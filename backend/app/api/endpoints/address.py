from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.address import AddressLog
from app.schemas.address import AddressCreate, AddressResponse, NormalizationResult

router = APIRouter()

from app.services.juso_service import juso_service
from app.services.llm_service import llm_service
from app.services.local_search import LocalSearchService
from app.db.session import SessionLocal

def _normalize_logic(raw: str) -> NormalizationResult:
    """
    Local-Only Normalization Logic
    Flow: Local DB -> (fail) -> LLM Correction -> Local DB -> (fail) -> Error
    """
    db = SessionLocal()
    local_service = LocalSearchService(db)
    
    try:
        # 1. First Attempt: Local DB Search
        local_result = local_service.search(raw)
        if local_result:
            print(f"DEBUG: Local Hit! {local_result.refined_address}")
            return local_result

        # 2. If Failed, Try LLM Correction (Local Ollama)
        print(f"DEBUG: Attempting AI Correction for: {raw}")
        corrected_text = llm_service.correct_address(raw)
        
        if corrected_text and corrected_text != raw:
            print(f"DEBUG: AI Suggested: {corrected_text}")
            
            # Retry Local Search with Corrected Text
            retry_result = local_service.search(corrected_text)
            if retry_result:
                retry_result.is_ai_corrected = True
                retry_result.message = f"Matched via Local DB (AI Fixed: {corrected_text})"
                return retry_result
                
    except Exception as e:
        print(f"Normalization Error: {e}")
    finally:
        db.close()

    # 3. Fallback / Failure
    return NormalizationResult(
        success=False,
        is_ai_corrected=False,
        message="Address not found in Local DB."
    )
            
    return NormalizationResult(
        success=False,
        is_ai_corrected=False,
        message=f"Address not found. Final Error: {search_result.get('error')}"
    )

@router.post("/normalize", response_model=AddressResponse)
def normalize_address(
    input_data: AddressCreate,
    db: Session = Depends(get_db)
):
    """
    Normalize Address (주소 정제 요청)
    - Receives a raw string.
    - Processes it through the normalization pipeline.
    - Saves the log to DB.
    """
    # 1. Logic (로직 수행)
    result = _normalize_logic(input_data.raw_text)
    
    
    # 2. Save to DB (DB 저장)
    db_obj = AddressLog(
        raw_text=input_data.raw_text,
        refined_text=result.refined_address,
        road_addr=result.road_address,
        jibun_addr=result.jibun_address,
        zip_no=result.zip_code,
        
        # Detailed Fields
        si_nm=result.si_nm,
        sgg_nm=result.sgg_nm,
        emd_nm=result.emd_nm,
        buld_nm=result.buld_nm,
        bd_mgt_sn=result.bd_mgt_sn,
        
        is_ai_corrected=result.is_ai_corrected,
        status="success" if result.success else "fail",
        error_message=result.message if not result.success else None
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    return db_obj

@router.get("/history", response_model=List[AddressResponse])
def read_history(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get History (이력 조회)
    """
    logs = db.query(AddressLog).offset(skip).limit(limit).all()
    return logs

@router.get("/search")
def search_address_candidates(query: str, limit: int = 10, db: Session = Depends(get_db)):
    """
    Search Address Candidates (주소 후보 검색)
    - Returns a list of matching addresses for user selection.
    - Useful for building name searches like '우림라이온스밸리'.
    """
    local_service = LocalSearchService(db)
    candidates = local_service.search_candidates(query, limit=limit)
    
    return {
        "query": query,
        "count": len(candidates),
        "candidates": candidates
    }

@router.post("/bulk-normalize")
async def bulk_normalize_address(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk Normalize from CSV
    - Expects a CSV file with a column named 'address' or the first column will be used.
    - Returns a CSV file with appended columns.
    """
    from app.utils.csv_handler import read_csv_file, df_to_csv_bytes
    from fastapi.responses import StreamingResponse
    import io
    import pandas as pd
    
    # 1. Read CSV
    try:
        df = read_csv_file(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
    
    # 2. Identify Address Column
    # Check for likely names ['address', 'juso', 'addr', '주소']
    target_col = None
    candidates = ['address', 'addr', 'juso', '주소', 'raw_text']
    
    for col in df.columns:
        if col.lower() in candidates:
            target_col = col
            break
            
    if not target_col:
        # Fallback to first column
        target_col = df.columns[0]

    # 3. Process Rows (Synchronous for now, intended for small batches < 1000)
    results = []
    
    # Pre-calculate to avoid DB overhead per row if possible, 
    # but for logging we might want to save. Let's just process purely first.
    
    for idx, row in df.iterrows():
        raw_addr = str(row[target_col])
        res = _normalize_logic(raw_addr)
        
        # Determine status/error for CSV
        status_val = "success" if res.success else "fail"
        err_val = res.message if not res.success else ""
        
        results.append({
            "refined_address": res.refined_address,
            "road_address": res.road_address,
            "zip_code": res.zip_code,
            "si_nm": res.si_nm,
            "sgg_nm": res.sgg_nm,
            "buld_nm": res.buld_nm,
            "status": status_val,
            "error_info": err_val
        })
        
    # 4. Append Results to DataFrame
    result_df = pd.DataFrame(results)
    final_df = pd.concat([df.reset_index(drop=True), result_df], axis=1)
    
    # 5. Prepare Response
    # Convert to list of dicts for JSON response (replace NaN with empty string)
    data_list = final_df.fillna("").to_dict(orient="records")
    
    # Generate CSV string for client-side download
    # Using utf-8-sig for Excel compatibility
    csv_buffer = io.StringIO()
    final_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    csv_content = csv_buffer.getvalue()

    return {
        "count": len(data_list),
        "results": data_list,
        "csv_content": csv_content,
        "filename": f"refined_{file.filename}"
    }

@router.get("/debug-db")
def debug_local_db(q: str = "테헤란로", db: Session = Depends(get_db)):
    """
    Debug Local DB Content
    """
    from app.models.local_address import AddressMaster
    
    count = db.query(AddressMaster).count()
    
    # Sample search
    results = db.query(AddressMaster).filter(AddressMaster.road_nm.like(f"%{q}%")).limit(10).all()
    
    sample_data = []
    for r in results:
        sample_data.append({
            "id": r.id,
            "road": r.road_nm,
            "main": r.buld_mainsn,
            "full": r.road_full_addr,
            "sido": r.si_nm
        })
        
    return {
        "total_count": count,
        "search_query": q,
        "found_count": len(sample_data),
        "samples": sample_data
    }
