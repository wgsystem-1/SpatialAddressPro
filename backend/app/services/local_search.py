from sqlalchemy.orm import Session
from app.models.local_address import AddressMaster
from app.schemas.address import NormalizationResult
from sqlalchemy import or_
import re

class LocalSearchService:
    # 특례시 매핑 (양방향)
    SPECIAL_CITY_MAP = {
        "수원특례시": "수원시",
        "용인특례시": "용인시",
        "고양특례시": "고양시",
        "창원특례시": "창원시",
        # 역방향
        "수원시": "수원특례시",
        "용인시": "용인특례시",
        "고양시": "고양특례시",
        "창원시": "창원특례시",
    }

    # 시도명 매핑 (약어/별칭 포함)
    SIDO_MAP = {
        "서울": "서울특별시", "서울특별시": "서울특별시",
        "부산": "부산광역시", "부산광역시": "부산광역시",
        "대구": "대구광역시", "대구광역시": "대구광역시",
        "인천": "인천광역시", "인천광역시": "인천광역시",
        "광주": "광주광역시", "광주광역시": "광주광역시",
        "대전": "대전광역시", "대전광역시": "대전광역시",
        "울산": "울산광역시", "울산광역시": "울산광역시",
        "세종": "세종특별자치시", "세종시": "세종특별자치시", "세종특별자치시": "세종특별자치시",
        "경기": "경기도", "경기도": "경기도",
        "강원": "강원특별자치도", "강원도": "강원특별자치도", "강원특별자치도": "강원특별자치도",
        "충북": "충청북도", "충청북도": "충청북도",
        "충남": "충청남도", "충청남도": "충청남도",
        "전북": "전북특별자치도", "전라북도": "전북특별자치도", "전북특별자치도": "전북특별자치도",
        "전남": "전라남도", "전라남도": "전라남도",
        "경북": "경상북도", "경상북도": "경상북도",
        "경남": "경상남도", "경상남도": "경상남도",
        "제주": "제주특별자치도", "제주도": "제주특별자치도", "제주특별자치도": "제주특별자치도"
    }
    
    def _parse_region_hints(self, tokens: list[str]) -> tuple[str | None, str | None]:
        """토큰 목록에서 시도/시군구 힌트를 추출"""
        sido_hint = None
        sgg_hint = None
        
        for i, t in enumerate(tokens):
            # 도로명은 제외 (예: 세종대로에서 '세종'이 시도로 인식되는 것 방지)
            if t.endswith('로') or t.endswith('길') or t.endswith('대로'):
                continue
            
            # 1. 시도 검색
            found_sido = False
            for alias, full_name in self.SIDO_MAP.items():
                if t == alias or t.startswith(alias):
                    # '제주'로 시작하는 '제주시' 같은 경우, '제주'는 시도로, '제주시'에서 '제주'를 뺀 '시'가 남음
                    # 하지만 보통 '제주 제주시'로 입력하므로 t == alias 체크가 안전
                    if t == alias or t == full_name:
                        sido_hint = full_name
                        found_sido = True
                        break
                    elif len(t) > len(alias):
                        # '제주제주시' 같은 경우 처리
                        rem = t[len(alias):]
                        if rem.endswith('시') or rem.endswith('군') or rem.endswith('구'):
                            sido_hint = full_name
                            sgg_hint = rem
                            found_sido = True
                            break
            
            if found_sido:
                continue

            # 2. 시군구 검색 (시도 검색 안 된 경우)
            if len(t) > 1 and (t.endswith('시') or t.endswith('군') or t.endswith('구')):
                # '광역시', '특별' 등은 시도가 아니므로 제외
                if t not in self.SIDO_MAP.values() and "특별" not in t and "광역" not in t:
                    sgg_hint = t
        
        return sido_hint, sgg_hint
    
    def __init__(self, db: Session):
        self.db = db
    
    def _normalize_special_city(self, text: str) -> tuple[str, str | None]:
        """
        Normalize special city names for search.
        Returns: (normalized_text, alternative_sgg)
        - normalized_text: 검색어에서 특례시를 일반시로 변환
        - alternative_sgg: DB 검색 시 사용할 대체 시군구명
        """
        alt_sgg = None
        result = text
        
        for special, normal in [
            ("수원특례시", "수원시"),
            ("용인특례시", "용인시"),
            ("고양특례시", "고양시"),
            ("창원특례시", "창원시"),
        ]:
            if special in text:
                result = text.replace(special, normal)
                alt_sgg = special
            elif normal in text:
                alt_sgg = special  # DB에는 특례시로 저장되어 있을 수 있음
        
        return result, alt_sgg

    def _normalize_hancha_numbers(self, text: str) -> str:
        """
        한자어 숫자 표현(일동, 이동...)을 아라비아 숫자로 변환
        예: 일도이동 -> 일도2동, 중앙동일가 -> 중앙동1가
        """
        # (구역명)(한자숫자)(동/가/로) 패턴 매칭
        # 예: 일도(이)(동) -> 일도2동
        hancha_map = {
            "일": "1", "이": "2", "삼": "3", "사": "4", "오": "5",
            "육": "6", "칠": "7", "팔": "8", "구": "9", "십": "10"
        }
        
        result = text
        for kor, num in hancha_map.items():
            # (글자들)(일/이/삼...)(동/가/로) 형태를 찾아서 변환
            # 예: 일도이동 -> 일도2동, 중앙동일가 -> 중앙동1가, 종로이가 -> 종로2가
            # 단어 끝이거나 공백, 숫자 앞인 경우만 변환
            pattern = f"([가-힣]+){kor}([동가로])(?=\\s|$|[0-9])"
            result = re.sub(pattern, f"\\g<1>{num}\\g<2>", result)
            
        return result

    def _insert_spaces(self, text: str) -> str:
        """
        Insert spaces in concatenated address strings.
        e.g., "부산광역시남구수영로305" → "부산광역시 남구 수영로 305"
        """
        # If already has spaces, return as-is
        if ' ' in text:
            return text
        
        result = text
        
        # Insert space AFTER these patterns (Korean administrative boundaries)
        patterns = [
            (r'(특별시)', r'\1 '),
            (r'(광역시)', r'\1 '),
            (r'(특별자치시)', r'\1 '),
            (r'(특별자치도)', r'\1 '),
            (r'([가-힣]+도)(?=[가-힣])', r'\1 '),  # 경기도, 충청북도 등
            (r'([가-힣]+시)(?=[가-힣]+[구군동])', r'\1 '),  # XX시 다음에 구/군/동이 오면
            (r'([가-힣]+구)(?=[가-힣])', r'\1 '),  # 남구, 해운대구 등
            (r'([가-힣]+군)(?=[가-힣])', r'\1 '),
            (r'([가-힣]+읍)(?=[가-힣])', r'\1 '),
            (r'([가-힣]+면)(?=[가-힣])', r'\1 '),
            (r'([가-힣]+동)(?=[가-힣]+로|[가-힣]+길|\d)', r'\1 '),  # 동 다음에 로/길/숫자
            (r'([가-힣]+로)(?=\d)', r'\1 '),  # 수영로305 → 수영로 305
            (r'([가-힣]+길)(?=\d)', r'\1 '),  # XX길123 → XX길 123
            (r'([가-힣]+대로)(?=\d)', r'\1 '),  # 세종대로175 → 세종대로 175
        ]
        
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result

    def search(self, raw_query: str) -> NormalizationResult | None:
        """
        Search address in local DB using basic parsing and LIKE query.
        This is much faster than external API.
        """
        # 0-A. Preprocess: Insert spaces in concatenated input
        # e.g., "부산광역시남구수영로305" → "부산광역시 남구 수영로 305"
        processed_query = self._insert_spaces(raw_query)
        if processed_query != raw_query:
            print(f"[DEBUG] Space insertion: '{raw_query}' → '{processed_query}'")
        raw_query = processed_query
        
        # 0-A2. Normalize special cities (특례시 처리)
        # e.g., "수원시" → also search "수원특례시"
        raw_query, alt_sgg = self._normalize_special_city(raw_query)
        if alt_sgg:
            print(f"[DEBUG] Special city detected: alt_sgg='{alt_sgg}'")
            
        # 0-A3. Normalize Hancha numbers (일동 -> 1동)
        raw_query = self._normalize_hancha_numbers(raw_query)
        
        # 0-B. Preprocess: Extract bracket content (reference info)
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
        
        # Strip "번지" from numbers like "329-10번지" -> "329-10"
        clean_query = re.sub(r'(\d+(?:-\d+)?)\s*번지', r'\1', clean_query)
        
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
                        # Preserve full number string including sub-number
                        if num_match.group(2):
                            road_num = f"{num_match.group(1)}-{num_match.group(2)}"
                        else:
                            road_num = num_match.group(1)
                        break
        
        # Fallback: Check last numeric token
        if not road_num:
            for token in reversed(tokens):
                num_match = re.match(r'^(\d+)(?:-(\d+))?$', token)
                if num_match:
                    # Preserve full number string
                    if num_match.group(2):
                        road_num = f"{num_match.group(1)}-{num_match.group(2)}"
                    else:
                        road_num = num_match.group(1)
                    break
        
        # Extract road name (scan parts)
        # Extract road name (scan parts)
        # Also try to extract Region (Sido) and District (Sgg) for better filtering
        # 1.1 Extract Region (Sido) and District (Sgg) for better filtering
        sido_hint, sgg_hint = self._parse_region_hints(tokens)

        # Helper to check if string contains Korean
        def has_korean(text):
            return any(ord('가') <= ord(c) <= ord('힣') for c in text)

        for i, t in enumerate(tokens):
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

        # If no road name found, generic search is better to avoid matching 
        # arbitrary roads by building number alone (especially common with Jibun addresses)
        if not road_name:
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
            # Handle special city mapping (특례시 ↔ 일반시)
            alt_sgg_for_query = self.SPECIAL_CITY_MAP.get(sgg_hint)
            if alt_sgg_for_query:
                # Search both: 수원시 OR 수원특례시
                query = query.filter(or_(
                    AddressMaster.sgg_nm.like(f"%{sgg_hint}%"),
                    AddressMaster.sgg_nm.like(f"%{alt_sgg_for_query}%")
                ))
            else:
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
        emd_hint = None
        
        # Clean raw text properly FIRST
        # Preserve hyphens for house numbers (e.g., 329-10)
        clean_text = re.sub(r'[^\w\s\-]', ' ', raw).strip()
        # Strip "번지" from tokens like "329-10번지"
        clean_text = re.sub(r'(\d+(?:-\d+)?)\s*번지', r'\1', clean_text)
        
        while '  ' in clean_text: clean_text = clean_text.replace('  ', ' ')
        tokens = clean_text.split()
        
        sido_hint, sgg_hint = self._parse_region_hints(tokens)

        for t in tokens:
             # Detect Dong (EMD) - must end with '동' and NOT start with digits (to avoid building dong like 205동)
             if len(t) > 1 and t.endswith('동') and not t[0].isdigit():
                 # Don't overwrite if we already found a likely EMD (EMD usually comes first)
                 if not emd_hint:
                     emd_hint = t


        
        is_jibun_likely = any(t.endswith("동") or t.endswith("리") or t.endswith("가") or t.endswith("읍") or t.endswith("면") for t in tokens)

        # 2. Extract core tokens (up to the first number token)
        # This helps ignore "tail" info like "101ho", "building name" etc.
        core_tokens = []
        for t in tokens:
            # If token is a number (e.g. 329-10)
            if re.match(r'^\d+(?:-\d+)?$', t):
                core_tokens.append(t)
                break
            # Skip region hints already captured
            if t == sido_hint or t == sgg_hint:
                continue
            
            # To handle "일도2동" vs "일도이동", replace digits with %
            # This makes "일도2동" -> "일도%동" or "일도이동" -> "일도%동"
            clean_t = re.sub(r'(\d+|일|이|삼|사|오|육|칠|팔|구|십)', '%', t)
            core_tokens.append(clean_t)
        
        if not core_tokens:
            return None
            
        core_query_part = "%".join(core_tokens)
        
        # 3. Tiered Search
        def try_search(use_sido=True, use_sgg=True):
            q = self.db.query(AddressMaster)
            if use_sido and sido_hint:
                q = q.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
            if use_sgg and sgg_hint:
                q = q.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
            
            # Separate text and number parts
            text_part = "%".join(core_tokens[:-1])
            num_part = core_tokens[-1]
            
            # Since jibun_full_addr usually ends with " [Main]-[Sub]",
            # we try strict match with a leading space to avoid matching 1069-1 when searching 9-1.
            
            if is_jibun_likely:
                # 1. Strict number match (preceded by space AND ends with the number)
                # This prevents '1506' from matching '1506-11'
                res = q.filter(AddressMaster.jibun_full_addr.like(f"%{text_part}% {num_part}")).first()
                if not res:
                    # 2. Fallback to loose match only if strict fails
                    res = q.filter(AddressMaster.jibun_full_addr.like(f"%{text_part}% {num_part}%")).first()
                if not res:
                    res = q.filter(AddressMaster.road_full_addr.like(f"%{text_part}%{num_part}%")).first()
            else:
                # Road search preferred - also try strict first
                res = q.filter(AddressMaster.road_full_addr.like(f"%{text_part}% {num_part}")).first()
                if not res:
                    res = q.filter(AddressMaster.road_full_addr.like(f"%{text_part}%{num_part}%")).first()
                if not res:
                    res = q.filter(AddressMaster.jibun_full_addr.like(f"%{text_part}%{num_part}%")).first()
            return res

        # Attempt 1: Full context
        match = try_search(True, True)
        if not match:
            # Attempt 2: Relax Sido (Maybe just "제주시 ...")
            match = try_search(False, True)
        if not match:
            # Attempt 3: Relax All Region (Last resort)
            match = try_search(False, False)

        if match:
            return self._to_result(match)

        # 3. Building Name Search (Smart Fallback)
        # Filter tokens that are likely details (X동, X호, X단지 if preceded by number)
        detail_patterns = [r'\d+동$', r'\d+호$', r'\d+층$', r'\d+단지$']
        build_tokens = []
        for t in tokens:
            if t in [sido_hint, sgg_hint, emd_hint]: continue
            if any(re.match(p, t) for p in detail_patterns): continue
            # If it's the house number already used in try_search, skip it? 
            # Actually build_tokens should be pure building names.
            if re.match(r'^\d+(?:-\d+)?$', t): continue
            build_tokens.append(t)
        
        if build_tokens:
            def try_build_step(tokens_to_use):
                query_str = "%".join(tokens_to_use)
                print(f"[DEBUG] Building Search: query={query_str}, hints=({sido_hint}, {sgg_hint}, {emd_hint})")
                
                def run_q(use_sido=True, use_sgg=True, use_emd=True):
                    from sqlalchemy import func
                    q = self.db.query(AddressMaster)
                    if use_sido and sido_hint: q = q.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
                    if use_sgg and sgg_hint: q = q.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
                    if use_emd and emd_hint: q = q.filter(AddressMaster.emd_nm.like(f"%{emd_hint}%"))
                    
                    # Space-insensitive matching
                    stripped = query_str.replace("%", "").replace(" ", "")
                    if stripped:
                        q = q.filter(func.replace(AddressMaster.buld_nm, ' ', '').like(f"%{stripped}%"))
                        return q.first()
                    return None

                # Tiered region matching for building
                m = run_q(True, True, True)
                if not m: m = run_q(True, True, False)
                if not m: m = run_q(False, True, False)
                if not m: m = run_q(False, False, False)
                return m

            # Attempt 1: Full building name tokens
            match = try_build_step(build_tokens)
            if match: return self._to_result(match)
            
            # Attempt 2: If many tokens, try just the first 2 (often the main apartment name)
            if len(build_tokens) > 2:
                print(f"[DEBUG] Falling back to first 2 building tokens: {build_tokens[:2]}")
                match = try_build_step(build_tokens[:2])
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
            bd_mgt_sn=obj.mgmt_no,
            is_ai_corrected=False,
            message="Matched via Local DB (Fast)"
        )

    def search_candidates(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search for address candidates matching the query.
        Prioritizes: Road+Number > Building Name > Full text search
        """
        # Apply space insertion for concatenated input
        query = self._insert_spaces(query)
        
        # Apply Hancha number normalization
        query = self._normalize_hancha_numbers(query)
        
        # Clean query
        clean_query = re.sub(r'[^\w\s\-]', ' ', query).strip()
        while '  ' in clean_query:
            clean_query = clean_query.replace('  ', ' ')
        
        tokens = clean_query.split()
        if not tokens:
            return []
        
        print(f"[DEBUG] search_candidates: tokens={tokens}")
        
        # Parse components
        road_name = None
        road_num = None
        detail_dong = None  # 201동 같은 상세주소
        building_name_hint = None
        
        sido_hint, sgg_hint = self._parse_region_hints(tokens)
        
        for i, t in enumerate(tokens):
            # Road name detection (ends with 로/길/대로)
            if t.endswith('로') or t.endswith('길') or t.endswith('대로'):
                road_name = t
                # Check next token for number
                if i + 1 < len(tokens):
                    next_t = tokens[i + 1]
                    num_match = re.match(r'^(\d+)(?:-(\d+))?', next_t)
                    if num_match:
                        road_num = int(num_match.group(1))
            
            # Pure number (could be building number)
            elif re.match(r'^\d+$', t) and not road_num:
                road_num = int(t)
            
            # Detail dong pattern (숫자+동 like 201동, 101동)
            elif re.match(r'^\d+동$', t):
                detail_dong = t
            
            # Building name hint (korean characters, not road, not num, not sido/sgg)
            # If token is not already identified as something else
            elif len(t) > 1 and not road_name and not road_num and not detail_dong:
                # If it's not the sido/sgg we already found
                if t != sido_hint and t != sgg_hint:
                    building_name_hint = t
        
        print(f"[DEBUG] Parsed: road={road_name}, num={road_num}, detail_dong={detail_dong}, building={building_name_hint}, sido={sido_hint}, sgg={sgg_hint}")
        
        candidates = []
        
        # Strategy 1: Road Name + Number search (most precise)
        if road_name and road_num:
            q = self.db.query(AddressMaster)
            q = q.filter(AddressMaster.road_nm == road_name)
            q = q.filter(AddressMaster.buld_mainsn == road_num)
            
            if sido_hint:
                q = q.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
            if sgg_hint:
                alt_sgg = self.SPECIAL_CITY_MAP.get(sgg_hint)
                if alt_sgg:
                    q = q.filter(or_(
                        AddressMaster.sgg_nm.like(f"%{sgg_hint}%"),
                        AddressMaster.sgg_nm.like(f"%{alt_sgg}%")
                    ))
                else:
                    q = q.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
            
            results = q.limit(limit * 5).all()
            
            # Deduplicate
            seen = set()
            for r in results:
                key = f"{r.road_full_addr}|{r.buld_nm}"
                if key not in seen:
                    seen.add(key)
                    candidates.append(self._to_candidate(r))
                    if len(candidates) >= limit:
                        break
        
        # Strategy 2: Road Name only (if no number or Strategy 1 failed)
        if not candidates and road_name:
            q = self.db.query(AddressMaster)
            q = q.filter(AddressMaster.road_nm.like(f"%{road_name}%"))
            
            if sido_hint:
                q = q.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
            if sgg_hint:
                alt_sgg = self.SPECIAL_CITY_MAP.get(sgg_hint)
                if alt_sgg:
                    q = q.filter(or_(
                        AddressMaster.sgg_nm.like(f"%{sgg_hint}%"),
                        AddressMaster.sgg_nm.like(f"%{alt_sgg}%")
                    ))
                else:
                    q = q.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
            
            results = q.limit(limit * 5).all()
            
            seen = set()
            for r in results:
                key = f"{r.road_full_addr}"
                if key not in seen:
                    seen.add(key)
                    candidates.append(self._to_candidate(r))
                    if len(candidates) >= limit:
                        break
        
        # Strategy 3: Building name search
        if not candidates and building_name_hint:
            q = self.db.query(AddressMaster)
            q = q.filter(AddressMaster.buld_nm.like(f"%{building_name_hint}%"))
            
            if sido_hint:
                q = q.filter(AddressMaster.si_nm.like(f"{sido_hint}%"))
            if sgg_hint:
                alt_sgg = self.SPECIAL_CITY_MAP.get(sgg_hint)
                if alt_sgg:
                    q = q.filter(or_(
                        AddressMaster.sgg_nm.like(f"%{sgg_hint}%"),
                        AddressMaster.sgg_nm.like(f"%{alt_sgg}%")
                    ))
                else:
                    q = q.filter(AddressMaster.sgg_nm.like(f"%{sgg_hint}%"))
            
            results = q.limit(limit * 5).all()
            
            seen = set()
            for r in results:
                key = f"{r.buld_nm}|{r.sgg_nm}"
                if key not in seen:
                    seen.add(key)
                    candidates.append(self._to_candidate(r))
                    if len(candidates) >= limit:
                        break
        
        # Strategy 4: Fallback to building name search with any token
        if not candidates:
            # Find longest non-numeric, non-region token
            search_tokens = [t for t in tokens 
                           if not re.match(r'^\d+동?$', t) 
                           and t not in [sido_hint, sgg_hint]
                           and not t.endswith('로') and not t.endswith('길')]
            
            if search_tokens:
                main_token = max(search_tokens, key=len)
                
                q = self.db.query(AddressMaster)
                q = q.filter(AddressMaster.buld_nm.like(f"%{main_token}%"))
                
                results = q.limit(limit * 5).all()
                
                seen = set()
                for r in results:
                    key = f"{r.buld_nm}|{r.sgg_nm}"
                    if key not in seen:
                        seen.add(key)
                        candidates.append(self._to_candidate(r))
                        if len(candidates) >= limit:
                            break
        
        print(f"[DEBUG] search_candidates: found {len(candidates)} candidates")
        return candidates

    def _to_candidate(self, r: AddressMaster) -> dict:
        """Convert AddressMaster to candidate dict"""
        return {
            "id": r.id,
            "road_address": r.road_full_addr,
            "jibun_address": r.jibun_full_addr,
            "building_name": r.buld_nm or "",
            "zip_code": r.zip_no,
            "si_nm": r.si_nm,
            "sgg_nm": r.sgg_nm,
            "emd_nm": r.emd_nm
        }

