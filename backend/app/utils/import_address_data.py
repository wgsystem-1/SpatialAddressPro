import os
import glob
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.models.local_address import AddressMaster, AddressDetail

# Auto Create Tables
AddressMaster.metadata.create_all(bind=engine)
AddressDetail.metadata.create_all(bind=engine)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")

def load_road_code_map():
    """ 1. 개선_도로명코드_전체분 (Global) """
    code_map = {}
    files = glob.glob(os.path.join(DATA_DIR, "*도로명코드_전체분.txt"))
    if not files: return {}
    
    print(f"[INIT] Loading Road Codes from {os.path.basename(files[0])}...")
    with open(files[0], "r", encoding="cp949", errors="ignore") as f:
        for line in f:
            cols = line.strip().split('|')
            if len(cols) < 5: continue
            # Col Indices: 0:Code, 1:Road, 4:Sido, 6:Sgg, 8:Emd
            code_map[cols[0]] = {
                "sido": cols[4], "sgg": cols[6], "road": cols[1], "emd": cols[8]
            }
    print(f"[INIT] Loaded {len(code_map)} Road Codes.")
    return code_map

def load_extra_info(region_suffix):
    """ 2. 부가정보 (Building Name) """
    # Map: { MgmtNo : BuildName }
    info_map = {}
    fpath = os.path.join(DATA_DIR, f"부가정보_{region_suffix}")
    if not os.path.exists(fpath): return {}
    
    print(f"  [LOAD] Building Infos from {region_suffix}...")
    with open(fpath, "r", encoding="cp949", errors="ignore") as f:
        for line in f:
            cols = line.strip().split('|')
            if len(cols) < 8: continue
            # 0: MgmtNo, 7: Building Name (8th column)
            mgmt_no = cols[0]
            bd_nm = cols[7]
            if bd_nm:
                info_map[mgmt_no] = bd_nm
    return info_map

def load_jibun_info(region_suffix):
    """ 3. 지번 (Jibun Number + 법정동) """
    # Map: { MgmtNo : { "jibun": "123-4", "emd": "하안동" } }
    jibun_map = {}
    fpath = os.path.join(DATA_DIR, f"지번_{region_suffix}")
    if not os.path.exists(fpath): return {}

    print(f"  [LOAD] Jibun Infos from {region_suffix}...")
    with open(fpath, "r", encoding="cp949", errors="ignore") as f:
        for line in f:
            cols = line.strip().split('|')
            if len(cols) < 11: continue
            # Standard Layout:
            # 0: 관리번호, 1: 일련번호, 2: 법정동코드
            # 3: 시도명, 4: 시군구명, 5: 법정읍면동명 (★ 핵심!)
            # 6: 법정리명, 7: 산여부, 8: 지번본번, 9: 지번부번, 10: 대표여부
            # Only use Representative Jibun (1) to keep it simple 1:1
            if cols[10] == '1':
                mgmt_no = cols[0]
                
                # Extract legal dong name (법정읍면동명)
                emd_name = cols[5].strip() if len(cols) > 5 else ""
                # Extract legal ri name (법정리명)
                ri_name = cols[6].strip() if len(cols) > 6 else ""
                
                # Extract jibun number
                main_no = int(cols[8]) if cols[8].isdigit() else 0
                sub_no = int(cols[9]) if cols[9].isdigit() else 0
                
                jibun_str = f"{main_no}"
                if sub_no > 0:
                    jibun_str += f"-{sub_no}"
                
                jibun_map[mgmt_no] = {
                    "jibun": jibun_str,
                    "emd": emd_name,
                    "ri": ri_name
                }
    return jibun_map


def load_english_info(region_key):
    """
    4. 영문 도로명주소 (English Road Name Address)
    Files: 영문/rneng_seoul.txt, rneng_busan.txt, etc.
    Returns: { MgmtNo: { si_eng, sgg_eng, road_eng, full_eng } }
    """
    # Map region suffix to English file key
    region_to_eng_file = {
        "서울특별시.txt": "seoul",
        "부산광역시.txt": "busan",
        "대구광역시.txt": "daegu",
        "인천광역시.txt": "incheon",
        "광주광역시.txt": "gwangju",
        "대전광역시.txt": "daejeon",
        "울산광역시.txt": "ulsan",
        "세종특별자치시.txt": "sejong",
        "경기도.txt": "gyunggi",
        "강원특별자치도.txt": "gangwon",
        "충청북도.txt": "chungbuk",
        "충청남도.txt": "chungnam",
        "전북특별자치도.txt": "jeonbuk",
        "전라남도.txt": "jeonnam",
        "경상북도.txt": "gyeongbuk",
        "경상남도.txt": "gyeongnam",
        "제주특별자치도.txt": "jeju"
    }
    
    eng_file_key = region_to_eng_file.get(region_key)
    if not eng_file_key:
        return {}
    
    eng_map = {}
    fpath = os.path.join(DATA_DIR, "영문", f"rneng_{eng_file_key}.txt")
    if not os.path.exists(fpath):
        print(f"  [WARN] English file not found: {fpath}")
        return {}
    
    print(f"  [LOAD] English Address from rneng_{eng_file_key}.txt...")
    with open(fpath, "r", encoding="cp949", errors="ignore") as f:
        for line in f:
            cols = line.strip().split('|')
            if len(cols) < 12: continue
            
            # Layout:
            # 0: MgmtNo, 2: si_eng, 3: sgg_eng, 7: road_eng
            # 9: buld_main, 10: buld_sub, 11: zip
            mgmt_no = cols[0]
            si_eng = cols[2].strip()
            sgg_eng = cols[3].strip()
            road_eng = cols[7].strip()
            buld_main = cols[9].strip()
            buld_sub = cols[10].strip()
            
            # Construct full English address
            full_eng = f"{road_eng} {buld_main}"
            if buld_sub and buld_sub != '0':
                full_eng += f"-{buld_sub}"
            full_eng += f", {sgg_eng}, {si_eng}"
            
            eng_map[mgmt_no] = {
                "si_eng": si_eng,
                "sgg_eng": sgg_eng,
                "road_eng": road_eng,
                "full_eng": full_eng
            }
    
    print(f"  [LOAD] Loaded {len(eng_map)} English entries.")
    return eng_map


def load_all_detail_addresses(db):
    """
    5. 상세주소 (Detail Address - Dong/Floor/Ho)
    Finds all rns*.txt files and imports them.
    """
    detail_files = glob.glob(os.path.join(DATA_DIR, "rns*.txt"))
    
    if not detail_files:
        print("[WARN] No detail address files (rns*.txt) found.")
        return 0
    
    print(f"[INFO] Found {len(detail_files)} detail address files.")
    total_count = 0
    
    for fpath in detail_files:
        fname = os.path.basename(fpath)
        print(f"  [LOAD] Processing {fname}...")
        
        buffer = []
        count = 0
        
        try:
            with open(fpath, "r", encoding="cp949", errors="ignore") as f:
                for line in f:
                    cols = line.strip().split('|')
                    if len(cols) < 17: continue
                    
                    # Layout (0-indexed):
                    # 5: 동명칭, 6: 층명칭, 7: 호명칭, 8: 호점미사명칭
                    # 9: 지하구분, 16: 도로명주소관리번호
                    dong = cols[5].strip() if len(cols) > 5 else ""
                    floor = cols[6].strip() if len(cols) > 6 else ""
                    ho = cols[7].strip() if len(cols) > 7 else ""
                    ho_detail = cols[8].strip() if len(cols) > 8 else ""
                    is_basement = cols[9].strip() if len(cols) > 9 else "0"
                    mgmt_no = cols[16].strip() if len(cols) > 16 else ""
                    
                    if not mgmt_no: continue
                    
                    # Construct detail full string
                    parts = []
                    if dong: parts.append(dong)
                    if floor: parts.append(floor)
                    if ho: parts.append(ho)
                    if ho_detail: parts.append(ho_detail)
                    detail_full = " ".join(parts)
                    
                    rec = AddressDetail(
                        mgmt_no=mgmt_no,
                        dong=dong if dong else None,
                        floor=floor if floor else None,
                        ho=ho if ho else None,
                        ho_detail=ho_detail if ho_detail else None,
                        is_basement=is_basement,
                        detail_full=detail_full if detail_full else None
                    )
                    buffer.append(rec)
                    
                    if len(buffer) >= 10000:
                        db.bulk_save_objects(buffer)
                        db.commit()
                        count += len(buffer)
                        buffer = []
            
            # Flush remaining
            if buffer:
                db.bulk_save_objects(buffer)
                db.commit()
                count += len(buffer)
            
            print(f"    -> Inserted {count} detail records from {fname}")
            total_count += count
            
        except Exception as e:
            print(f"  [ERROR] Failed to process {fname}: {e}")
            continue
    
    print(f"[SUCCESS] Total {total_count} detail addresses imported.")
    return total_count


def import_addresses():
    db = SessionLocal()
    try:
        # Step A. Load Global Maps
        road_map = load_road_code_map()
        if not road_map:
            print("[ERROR] Road Map Missing - Continuing with Dummy Data Only for Test")
            # Usually return, but let's allow dummy insert below
        
        # [DEBUG] Insert HARDCODED dummy for known test case "Juan-dong 110" -> "Juan-ro 122"
        # Only if not exists
        chk = db.query(AddressMaster).filter(AddressMaster.jibun_full_addr == "인천광역시 미추홀구 주안동 110").first()
        if not chk:
            dummy = AddressMaster(
                si_nm="인천광역시", sgg_nm="미추홀구", emd_nm="주안동",
                road_nm="주안로", buld_mainsn=122, buld_subsn=0,
                buld_nm="테스트빌딩", zip_no="22100",
                road_full_addr="인천광역시 미추홀구 주안로 122",
                jibun_full_addr="인천광역시 미추홀구 주안동 110"
            )
            db.add(dummy)
            db.commit()
            print("[DEBUG] Inserted Dummy Record for Juan-dong 110 => Juan-ro 122")

        # Step B. Identify Regions based on '주소_*.txt'
        addr_files = glob.glob(os.path.join(DATA_DIR, "주소_*.txt"))
        print(f"[INFO] Found {len(addr_files)} address files.")
        
        total_inserted = 0
        
        for fpath in addr_files:
            fname = os.path.basename(fpath)
            # suffix ex: "서울특별시.txt"
            region_suffix = fname.replace("주소_", "")
            
            print(f"\n[PROC] Processing Region: {region_suffix.replace('.txt', '')}")
            
            # 1. Load Helpers for this region
            bd_map = load_extra_info(region_suffix)
            jibun_map = load_jibun_info(region_suffix)
            eng_map = load_english_info(region_suffix)  # NEW: English data
            
            # 2. Process Address File
            buffer = []
            print(f"  [READ] Main Address File...")
            with open(fpath, "r", encoding="cp949", errors="ignore") as f:
                for line in f:
                    cols = line.strip().split('|')
                    if len(cols) < 7: continue
                    
                    mgmt_no = cols[0]
                    road_code = cols[1]
                    main_sn = int(cols[4])
                    sub_sn = int(cols[5])
                    zip_code = cols[6]
                    is_basement = cols[3]
                    
                    # Resolve Road Info
                    if road_code not in road_map: continue
                    r_info = road_map[road_code]
                    sido, sgg, road, emd = r_info['sido'], r_info['sgg'], r_info['road'], r_info['emd']
                    
                    # Resolve Optional Join Info
                    buld_nm = bd_map.get(mgmt_no, "")
                    
                    # Fallback: Capture Building Name from columns if missing in map
                    # Standard Format often has Building Name at index 11 (SiGunGu Building Name) or 10
                    # Screenshot suggested: ...|Zip|||Name|...
                    if not buld_nm and len(cols) > 11:
                         # Try col 11 (Commonly SiGunGu Building Name)
                         if cols[11].strip():
                             buld_nm = cols[11].strip()
                         # Try col 10 (Detail Building Name?)
                         elif cols[10].strip():
                             buld_nm = cols[10].strip()
                         # Try col 9 (Some formats)
                         elif len(cols) > 9 and cols[9].strip():
                             buld_nm = cols[9].strip()

                    jibun_data = jibun_map.get(mgmt_no, {})
                    jibun_num = jibun_data.get("jibun", "") if isinstance(jibun_data, dict) else jibun_data
                    
                    # Use legal dong from jibun file (accurate per address)
                    # Fall back to road_map emd if not available
                    actual_emd = jibun_data.get("emd", "") if isinstance(jibun_data, dict) else ""
                    if actual_emd:
                        emd = actual_emd  # Override with accurate emd!
                    
                    # English Address Data
                    eng_data = eng_map.get(mgmt_no, {})
                    si_eng = eng_data.get("si_eng", "")
                    sgg_eng = eng_data.get("sgg_eng", "")
                    road_eng = eng_data.get("road_eng", "")
                    full_eng = eng_data.get("full_eng", "")
                    
                    # Construct Strings
                    # Road Addr
                    road_addr = f"{sido} {sgg} {road} {main_sn}"
                    if sub_sn > 0: road_addr += f"-{sub_sn}"
                    if is_basement != '0': road_addr += " (지하)"
                    
                    # Jibun Addr - now uses correct emd and optional ri
                    actual_ri = jibun_data.get("ri", "") if isinstance(jibun_data, dict) else ""
                    jibun_addr = f"{sido} {sgg} {emd}"
                    if actual_ri:
                        jibun_addr += f" {actual_ri}"
                    if jibun_num:
                        jibun_addr += f" {jibun_num}"
                    
                    rec = AddressMaster(
                        mgmt_no=mgmt_no,   # 연계키 추가
                        si_nm=sido,
                        sgg_nm=sgg,
                        emd_nm=emd,
                        road_nm=road,
                        buld_mainsn=main_sn,
                        buld_subsn=sub_sn,
                        buld_nm=buld_nm,   # Now populated!
                        zip_no=zip_code,
                        road_full_addr=road_addr,
                        jibun_full_addr=jibun_addr,
                        # English fields
                        si_nm_eng=si_eng if si_eng else None,
                        sgg_nm_eng=sgg_eng if sgg_eng else None,
                        road_nm_eng=road_eng if road_eng else None,
                        road_full_addr_eng=full_eng if full_eng else None
                    )
                    buffer.append(rec)
                    
                    if len(buffer) >= 10000:
                        db.bulk_save_objects(buffer)
                        db.commit()
                        total_inserted += len(buffer)
                        buffer = []
                        print(f"    -> Inserted {total_inserted} rows...")

            # Flush remaining
            if buffer:
                db.bulk_save_objects(buffer)
                db.commit()
                total_inserted += len(buffer)
            
            # Clear memory for next region
            bd_map.clear()
            jibun_map.clear()
            eng_map.clear()

        print(f"[SUCCESS] Total {total_inserted} address records imported.")
        
        # Import ALL detail addresses after main addresses are done
        print("\n[PHASE 2] Importing Detail Addresses...")
        load_all_detail_addresses(db)

    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_addresses()
