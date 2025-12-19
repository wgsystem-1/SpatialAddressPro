from sqlalchemy.orm import Session
from app.models.local_address import AddressMaster
from app.schemas.address import NormalizationResult
from sqlalchemy import or_
import re

class LocalSearchService:
    def __init__(self, db: Session):
        self.db = db

    def search(self, raw_query: str) -> NormalizationResult | None:
        """
        Search address in local DB using basic parsing and LIKE query.
        This is much faster than external API.
        """
        # 0. Preprocess: Extract bracket content (reference info)
        # Pattern: "[연동, 대림2차아파트]" or "(연동)" 
        bracket_content = ""
        ref_building_name = None
        
        # Extract [...] content
        bracket_match = re.search(r'\[([^\]]+)\]', raw_query)
        if bracket_match:
            bracket_content = bracket_match.group(1)
            # Try to extract building name from bracket (usually after comma)
            if ',' in bracket_content:
                parts = bracket_content.split(',')
                for p in parts:
                    p = p.strip()
                    if '아파트' in p or '빌딩' in p or '타워' in p or '밸리' in p or '센터' in p:
                        ref_building_name = p
                        break
                if not ref_building_name and len(parts) > 1:
                    ref_building_name = parts[-1].strip()  # Last part is often building name
            else:
                # Single item in bracket - could be dong or building
                if '동' not in bracket_content or '아파트' in bracket_content:
                    ref_building_name = bracket_content.strip()
        
        # Remove bracket content from query for cleaner parsing
        clean_query = re.sub(r'\[[^\]]+\]', ' ', raw_query)
        clean_query = re.sub(r'\([^\)]+\)', ' ', clean_query)  # Also remove ()
        
        # Handle numbers stuck to brackets: "25[연동]" -> "25 "
        clean_query = re.sub(r'(\d+)\s*\[', r'\1 ', clean_query)
        
        # Clean up multiple spaces
        clean_query = re.sub(r'\s+', ' ', clean_query).strip()
        
        # 1. Simple Parsing
        tokens = clean_query.split()
        if len(tokens) < 2:
            # Try with ref_building_name if available
            if ref_building_name:
                return self._search_by_building_name(ref_building_name)
            return None
            
        # Try to find 'Road Name' and 'Building Number'
        road_num = None
        road_name = None
        
        # Extract number from tokens (look for pattern like "연화로 25")
        for i, token in enumerate(tokens):
            # Check if this token ends with road suffix and next is number
            if any(token.endswith(suffix) for suffix in ['로', '길', '대로']):
                road_name = token
                # Check next token for number
                if i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    # Extract number (handle "25" or "25-1" or "25동" etc)
                    num_match = re.match(r'^(\d+)(?:-(\d+))?', next_token)
                    if num_match:
                        road_num = int(num_match.group(1))
                        break
        
        # Fallback: Check last numeric token
        if not road_num:
            for token in reversed(tokens):
                num_match = re.match(r'^(\d+)(?:-(\d+))?$', token)
                if num_match:
                    road_num = int(num_match.group(1))
                    break
        
        # Extract road name (scan parts)
        # Extract road name (scan parts)
        # Also try to extract Region (Sido) and District (Sgg) for better filtering
        sido_hint = None
        sgg_hint = None
        
        # Simple list of major Sido aliases for detection
        sido_aliases = {
            "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
            "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
            "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
            "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
            "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
            "경남": "경상남도", "제주": "제주특별자치도"
        }

        # Helper to check if string contains Korean
        def has_korean(text):
            return any(ord('가') <= ord(c) <= ord('힣') for c in text)

        for i, t in enumerate(tokens):
            # Detect Sido
            for alias, full_name in sido_aliases.items():
                if alias in t or full_name in t:
                    sido_hint = full_name
            
            # Detect Sgg
            if len(t) > 1 and (t.endswith('구') or t.endswith('군') or t.endswith('시')):
                if t not in sido_aliases.values() and "특별" not in t and "광역" not in t:
                    sgg_hint = t
            
            # Detect Road Name
            if t.endswith('로') or t.endswith('길'):
                # 1. If starts with digit (e.g. '1로', '3길'), merge with previous token!
                if t[0].isdigit() and i > 0:
                    # Check if previous token is NOT a Sigg/Sido
                    prev = tokens[i-1]
                    if not (prev.endswith('시') or prev.endswith('구') or prev.endswith('군')):
                         # Merge! (e.g. '디지털' + '1로' -> '디지털1로')
                         road_name = prev + t
                         # Maybe merge one more time? (e.g. '가산' + '디지털1로')
                         if i > 1:
                             prev2 = tokens[i-2]
                             if not (prev2.endswith('시') or prev2.endswith('구') or prev2.endswith('군')) and has_korean(prev2):
                                 road_name = prev2 + road_name
                else:
                    road_name = t
            
            # Detect Road Num (Digits or Digits-Digits)
            elif road_name and not road_num:
                # Match strict number pattern 10 or 10-10
                if re.match(r'^\d+(?:-\d+)?$', t):
                    road_num = t
                    print(f"[DEBUG] Assigned Num: {road_num} from token '{t}'")

        if not road_name and not road_num:
            return self._like_search(raw_query)

        # [DEBUG]
        print(f"[DEBUG] LocalSearch Parse: Road={road_name}, Num={road_num}, Sido={sido_hint}, Sgg={sgg_hint}")

        # 2. Query Construction
        query = self.db.query(AddressMaster)
        
        if road_name:
            # Try Exact Match first
            # Also try removing spaces from input road_name (e.g. '디지털 1로' -> '디지털1로')
            clean_road = road_name.replace(" ", "")
            if clean_road != road_name:
                query = query.filter(or_(AddressMaster.road_nm == road_name, AddressMaster.road_nm == clean_road))
            else:
                query = query.filter(AddressMaster.road_nm == road_name)
                
        if road_num:
            if isinstance(road_num, str) and '-' in road_num:
                main_s, sub_s = road_num.split('-')
                if main_s.isdigit() and sub_s.isdigit():
                    query = query.filter(AddressMaster.buld_mainsn == int(main_s))
                    query = query.filter(AddressMaster.buld_subsn == int(sub_s))
                else:
                    # Fallback if weird format
                    pass 
            elif str(road_num).isdigit():
                query = query.filter(AddressMaster.buld_mainsn == int(road_num))
                # If user typed "10", strictly "10-0".
                # But sometimes users omit sub 0.
                query = query.filter(AddressMaster.buld_subsn == 0)
        
        # Apply Regional Filters if detected
        if sido_hint:
            query = query.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
        if sgg_hint:
            # Sgg might be partial matching or fuzzy
            query = query.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))

        # Scoring Logic: Prioritize checks that match Sido/Sgg even if not explicitly filtered?
        # For now, just trust the filter.
            
        results = query.limit(10).all()
        
        # 2-1. Retry with Fuzzy Search if Road Name Exact Match Failed
        if not results and road_name:
            # Maybe AI dropped a number (e.g. 가산디지털1로 -> 가산디지털로)
            query_retry = self.db.query(AddressMaster)
            if road_num:
                if isinstance(road_num, str) and '-' in road_num:
                    main_s, sub_s = road_num.split('-')
                    if main_s.isdigit() and sub_s.isdigit():
                        query_retry = query_retry.filter(AddressMaster.buld_mainsn == int(main_s))
                        query_retry = query_retry.filter(AddressMaster.buld_subsn == int(sub_s))
                elif str(road_num).isdigit():
                    query_retry = query_retry.filter(AddressMaster.buld_mainsn == int(road_num))
                    # Usually fuzzy search implies we might be loose, but number should be exact
                    query_retry = query_retry.filter(AddressMaster.buld_subsn == 0)
            
            # Use LIKE '%road_name%' to catch '가산디지털1로' from '가산디지털로'
            # But be careful not to match too widely.
            query_retry = query_retry.filter(AddressMaster.road_nm.like(f"%{road_name}%"))
            
            if sido_hint:
                query_retry = query_retry.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
            if sgg_hint:
                query_retry = query_retry.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
                
            results = query_retry.limit(5).all()

        # 2-2. Retry with Building Name Search (Last Resort)
        if not results:
             # If input was like "은마아파트" or "GS타워"
             # Use ref_building_name from bracket if available
             query_build = self.db.query(AddressMaster)
             
             # Prioritize ref_building_name from brackets
             if ref_building_name:
                 target_name = ref_building_name
             elif road_name:
                 target_name = road_name
             else:
                 target_name = raw_query.replace(" ", "")
             
             # Filter by Sido/Sgg if known
             if sido_hint:
                query_build = query_build.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
             if sgg_hint:
                query_build = query_build.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
             
             # If we have road_num, also filter by it
             if road_num:
                 if isinstance(road_num, str) and '-' in road_num:
                     main_s = road_num.split('-')[0]
                     if main_s.isdigit():
                         query_build = query_build.filter(AddressMaster.buld_mainsn == int(main_s))
                 elif str(road_num).isdigit():
                     query_build = query_build.filter(AddressMaster.buld_mainsn == int(road_num))
                
             query_build = query_build.filter(AddressMaster.buld_nm.like(f"%{target_name}%"))
             results = query_build.limit(5).all()

        if not results:
             return self._like_search(raw_query)
             
        # 3. Handle Multiple Results
        best = results[0]
        final_res = self._to_result(best)
        
        # Populate candidates if more than 1 result
        if len(results) > 1:
            cands = []
            for r in results: # Include the best one too? Yes, usually.
                cands.append({
                    "road": r.road_nm,
                    "main": r.buld_mainsn,
                    "full": r.road_full_addr,
                    "sido": r.si_nm,
                    "sgg": r.sgg_nm,
                    "id": r.id
                })
            final_res.candidates = cands
            
        return final_res

    def _like_search(self, raw: str):
        # 1. Parse hints from raw text again just in case search logic bypassed parsing
        sido_hint = None
        sgg_hint = None
        emd_hint = None
        
        # Simple list of major Sido aliases for detection
        sido_aliases = {
            "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
            "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
            "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
            "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
            "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
            "경남": "경상남도", "제주": "제주특별자치도"
        }

        # Clean raw text properly FIRST
        clean_text = re.sub(r'[^\w\s]', ' ', raw).strip()
        while '  ' in clean_text: clean_text = clean_text.replace('  ', ' ')
        tokens = clean_text.split()
        
        for t in tokens:
             # Detect Sido
             for alias, full_name in sido_aliases.items():
                 if alias in t or full_name in t:
                     sido_hint = full_name
             
             # Detect Sgg
             if len(t) > 1 and (t.endswith('구') or t.endswith('군') or t.endswith('시')):
                 if t not in sido_aliases.values() and "특별" not in t and "광역" not in t:
                    sgg_hint = t
            
             # Detect Dong (EMD)
             if len(t) > 1 and t.endswith('동') and not t.isdigit():
                 emd_hint = t


        
        is_jibun_likely = any(t.endswith("동") or t.endswith("리") or t.endswith("가") for t in tokens)

        clean_raw = clean_text.replace(" ", "%")
        
        query = self.db.query(AddressMaster)
        
        # Apply strict filtering if region is detected
        if sido_hint:
             query = query.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
        if sgg_hint:
             query = query.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
        
        # Strategy: Determine if it's likely a Jibun Address (has 'Dong'/'Ri' but no Road Name parsed)
        # Since we are in _like_search, road_name parsing failed or was empty.
        
        if is_jibun_likely:
            # 1. Try Jibun Search FIRST
            match = query.filter(AddressMaster.jibun_full_addr.like(f"%{clean_raw}%")).first()
            
            # 2. If not found, try Road Search
            if not match:
                match = query.filter(AddressMaster.road_full_addr.like(f"%{clean_raw}%")).first()
        else:
            # Standard OR search (or Road first?)
            # Let's try Road first, then Jibun
            match = query.filter(AddressMaster.road_full_addr.like(f"%{clean_raw}%")).first()
            if not match:
                match = query.filter(AddressMaster.jibun_full_addr.like(f"%{clean_raw}%")).first()

        if match:
            return self._to_result(match)

        # 3. Building Name Search (Smart Fallback)
        # Construct building search term by removing detected region hints
        build_tokens = [t for t in tokens if t != sido_hint and t != sgg_hint and t != emd_hint]
        
        if build_tokens:
            build_name_query = "%".join(build_tokens)
            print(f"[DEBUG] Building Search: query={build_name_query}, hints=({sido_hint}, {sgg_hint}, {emd_hint})")
            
            # Helper to run query with optional filters
            # Enhanced to perform space-insensitive search on Building Name
            def try_build_search(use_sido=True, use_sgg=True, use_emd=True):
                from sqlalchemy import func
                q = self.db.query(AddressMaster)
                
                has_region_filter = False
                
                if use_sido and sido_hint:
                    q = q.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
                    has_region_filter = True
                if use_sgg and sgg_hint:
                    q = q.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
                    has_region_filter = True
                if use_emd and emd_hint:
                    # EMD filter is useful
                    q = q.filter(AddressMaster.emd_nm.like(f"%{emd_hint}%"))
                    has_region_filter = True
                
                # Performance Check: Only use Heavy Replace logic if we have regional filters
                # Global Search (no filters) with Function call is too slow.
                use_heavy = has_region_filter
                
                if use_heavy:
                     stripped_query = build_name_query.replace("%", "").replace(" ", "")
                     q = q.filter(func.replace(AddressMaster.buld_nm, ' ', '').like(f"%{stripped_query}%"))
                else:
                     # Standard Like for Global Search
                     q = q.filter(AddressMaster.buld_nm.like(f"%{build_name_query}%"))
                
                return q.first()

            # Attempt 1: Strict (All hints)
            match = try_build_search(True, True, True)
            if match: return self._to_result(match)
            
            # Attempt 2: Relax EMD (In case Dong is missing in DB or mismatches)
            if emd_hint:
                print(f"[DEBUG] Relaxing EMD filter...")
                match = try_build_search(True, True, False)
                if match: return self._to_result(match)

            # Attempt 3: Relax SGG (In case SGG mismatches)
            if sgg_hint:
                 print(f"[DEBUG] Relaxing SGG filter...")
                 match = try_build_search(True, False, False)
                 if match: return self._to_result(match)
            
            # Attempt 4: Search Only Building Name (Broadest)
            # Only do this if we have a reasonably specific building name (length check?)
            if len(build_name_query) > 2:
                 print(f"[DEBUG] Relaxing ALL region filters...")
                 match = try_build_search(False, False, False)
                 if match: return self._to_result(match)

        return None

    def _search_by_building_name(self, building_name: str) -> NormalizationResult | None:
        """
        Search by building name only (used when only bracket content is available)
        """
        query = self.db.query(AddressMaster)
        query = query.filter(AddressMaster.buld_nm.like(f"%{building_name}%"))
        result = query.first()
        if result:
            return self._to_result(result)
        return None

    def _to_result(self, obj: AddressMaster) -> NormalizationResult:
        road_str = f"{obj.si_nm} {obj.sgg_nm} {obj.road_nm} {obj.buld_mainsn}"
        if obj.buld_subsn > 0:
            road_str += f"-{obj.buld_subsn}"
            
        return NormalizationResult(
            success=True,
            refined_address=f"{road_str} ({obj.emd_nm})",
            road_address=road_str,
            jibun_address=obj.jibun_full_addr, # FIXED: jibun_addr -> jibun_full_addr
            zip_code=obj.zip_no,
            si_nm=obj.si_nm,
            sgg_nm=obj.sgg_nm,
            emd_nm=obj.emd_nm,
            buld_nm=obj.buld_nm,
            bd_mgt_sn=None,
            is_ai_corrected=False,
            message="Matched via Local DB (Fast)"
        )

    def search_candidates(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search for address candidates matching the query.
        Returns a list of candidate dictionaries for user selection.
        """
        from sqlalchemy import func
        
        # Clean query
        clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
        while '  ' in clean_query:
            clean_query = clean_query.replace('  ', ' ')
        
        tokens = clean_query.split()
        if not tokens:
            return []
        
        # Detect hints
        sido_aliases = {
            "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
            "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
            "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
            "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
            "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
            "경남": "경상남도", "제주": "제주특별자치도"
        }
        
        sido_hint = None
        sgg_hint = None
        
        for t in tokens:
            for alias, full_name in sido_aliases.items():
                if alias in t or full_name in t:
                    sido_hint = full_name
            if len(t) > 1 and (t.endswith('구') or t.endswith('군') or t.endswith('시')):
                if t not in sido_aliases.values() and "특별" not in t and "광역" not in t:
                    sgg_hint = t
        
        # Build search tokens (exclude detected hints)
        search_tokens = [t for t in tokens if t != sido_hint and t != sgg_hint]
        if not search_tokens:
            search_tokens = tokens  # Fallback to all tokens
        
        search_term = "%".join(search_tokens)
        
        # Query building names
        q = self.db.query(AddressMaster)
        
        if sido_hint:
            q = q.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
        if sgg_hint:
            q = q.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
        
        # Search in building name
        q = q.filter(AddressMaster.buld_nm.like(f"%{search_term}%"))
        
        # Get distinct building names to avoid duplicates (same building, different units)
        results = q.limit(limit * 5).all()  # Get more, then dedupe
        
        # Deduplicate by (road_full_addr)
        seen = set()
        candidates = []
        for r in results:
            key = r.road_full_addr
            if key not in seen:
                seen.add(key)
                candidates.append({
                    "id": r.id,
                    "road_address": r.road_full_addr,
                    "jibun_address": r.jibun_full_addr,
                    "building_name": r.buld_nm or "",
                    "zip_code": r.zip_no,
                    "si_nm": r.si_nm,
                    "sgg_nm": r.sgg_nm,
                    "emd_nm": r.emd_nm
                })
                if len(candidates) >= limit:
                    break
        
        return candidates

