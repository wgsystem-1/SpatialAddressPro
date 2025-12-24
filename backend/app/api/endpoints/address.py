from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.address import AddressLog
from app.schemas.address import AddressCreate, AddressResponse, NormalizationResult
import threading

router = APIRouter()

from app.services.juso_service import juso_service
from app.services.llm_service import llm_service
from app.services.local_search import LocalSearchService
from app.db.session import SessionLocal
import uuid
import time

# Session-based job management for concurrent bulk processing
class BulkJobManager:
    def __init__(self):
        self.jobs = {}  # {job_id: state_dict}
        self.lock = threading.Lock()
        self.max_jobs = 100  # Limit to prevent memory issues
        self.job_ttl = 3600  # 1 hour TTL for cleanup
    
    def create_job(self) -> str:
        """Create a new job and return its ID"""
        job_id = str(uuid.uuid4())[:8]
        with self.lock:
            # Cleanup old jobs if at limit
            self._cleanup_old_jobs()
            
            self.jobs[job_id] = {
                "is_running": True,
                "is_cancelled": False,
                "current_row": 0,
                "total_rows": 0,
                "created_at": time.time(),
                "results": None,  # Will store the final JSON data
                "filename": ""    # Original filename
            }
        return job_id
    
    def get_job(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)
    
    def update_job(self, job_id: str, **kwargs):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(kwargs)
    
    def cancel_job(self, job_id: str) -> bool:
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]["is_cancelled"] = True
                return True
            return False
    
    def finish_job(self, job_id: str, results=None):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]["is_running"] = False
                if results is not None:
                    self.jobs[job_id]["results"] = results
    
    def _cleanup_old_jobs(self):
        """Remove jobs older than TTL (1 hour)"""
        now = time.time()
        expired = [jid for jid, state in self.jobs.items() 
                   if now - state.get("created_at", 0) > self.job_ttl]
        for jid in expired:
            del self.jobs[jid]

# Global job manager instance
bulk_job_manager = BulkJobManager()


def _normalize_logic(raw: str, bulk_mode: bool = False) -> NormalizationResult:
    """
    Local-Only Normalization Logic
    Flow: Local DB -> (fail) -> LLM Correction -> Local DB -> (fail) -> Error
    
    bulk_mode: If True, skip LLM calls for faster processing
    """
    db = SessionLocal()
    local_service = LocalSearchService(db)
    
    try:
        # 1. First Attempt: Local DB Search
        local_result = local_service.search(raw)
        if local_result:
            print(f"DEBUG: Local Hit! {local_result.refined_address}")
            return local_result

        # 2. If bulk_mode, skip LLM and return immediately with needs_review status
        if bulk_mode:
            return NormalizationResult(
                success=False,
                is_ai_corrected=False,
                message="needs_review"  # Special marker for bulk mode failures
            )

        # 3. If Failed, Try LLM Correction (Local Ollama)
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

    # 4. Fallback / Failure
    return NormalizationResult(
        success=False,
        is_ai_corrected=False,
        message="Address not found in Local DB."
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

def _run_bulk_processing(job_id: str, df: "pd.DataFrame", target_col: str, filename: str):
    """Background worker for bulk processing"""
    import io
    import pandas as pd
    
    results = []
    try:
        for idx, row in df.iterrows():
            job = bulk_job_manager.get_job(job_id)
            if not job or job.get("is_cancelled"):
                break
                
            bulk_job_manager.update_job(job_id, current_row=idx + 1)
            
            raw_addr = str(row[target_col])
            res = _normalize_logic(raw_addr, bulk_mode=False) 
            
            if res.success:
                status_val = "success"
                err_val = "AI 보정 완료" if res.is_ai_corrected else ""
            else:
                status_val = "fail"
                err_val = res.message if res.message else "검색 실패"
            
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
            
        # Completion
        result_df = pd.DataFrame(results)
        final_df = pd.concat([df.reset_index(drop=True), result_df], axis=1)
        data_list = final_df.fillna("").to_dict(orient="records")
        
        csv_buffer = io.StringIO()
        final_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_content = csv_buffer.getvalue()

        bulk_job_manager.finish_job(job_id, results={
            "count": len(data_list),
            "results": data_list,
            "csv_content": csv_content,
            "filename": f"refined_{filename}"
        })
    except Exception as e:
        print(f"Bulk Background Error: {e}")
        bulk_job_manager.finish_job(job_id)


@router.post("/bulk-normalize")
async def bulk_normalize_address(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Bulk Normalize from CSV (Asynchronous)
    - Returns job_id immediately.
    """
    from app.utils.csv_handler import read_csv_file
    
    # 1. Read CSV
    try:
        df = read_csv_file(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
    
    # 1-1. Row Limit Check
    MAX_ROWS = 1000
    if len(df) > MAX_ROWS:
        raise HTTPException(
            status_code=400, 
            detail=f"CSV 파일이 너무 큽니다. 최대 {MAX_ROWS:,}건까지 처리 가능합니다."
        )
    
    # 2. Identify Address Column
    target_col = None
    candidates = ['address', 'addr', 'juso', '주소', 'raw_text']
    for col in df.columns:
        if col.lower() in candidates:
            target_col = col
            break
    if not target_col:
        target_col = df.columns[0]

    # 3. Create Job and Start Background Task
    job_id = bulk_job_manager.create_job()
    bulk_job_manager.update_job(job_id, total_rows=len(df), filename=file.filename)
    
    background_tasks.add_task(_run_bulk_processing, job_id, df, target_col, file.filename)
    
    return {"job_id": job_id, "message": "Bulk processing started."}

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


@router.get("/bulk-status/{job_id}")
async def get_bulk_status(job_id: str):
    """Get bulk processing status for a specific job"""
    job = bulk_job_manager.get_job(job_id)
    if not job:
        return {
            "is_running": False,
            "is_cancelled": False,
            "current_row": 0,
            "total_rows": 0,
            "progress_percent": 0,
            "error": "Job not found"
        }
    
    return {
        "is_running": job["is_running"],
        "is_cancelled": job["is_cancelled"],
        "current_row": job["current_row"],
        "total_rows": job["total_rows"],
        "progress_percent": (
            round(job["current_row"] / job["total_rows"] * 100, 1)
            if job["total_rows"] > 0 else 0
        ),
        "results_data": job.get("results") # This will be present only when is_running is False
    }


@router.post("/bulk-cancel/{job_id}")
async def cancel_bulk_processing(job_id: str):
    """Cancel ongoing bulk processing for a specific job"""
    job = bulk_job_manager.get_job(job_id)
    if not job:
        return {"success": False, "message": "Job을 찾을 수 없습니다."}
    
    if not job["is_running"]:
        return {"success": False, "message": "현재 진행 중인 처리가 없습니다."}
    
    bulk_job_manager.cancel_job(job_id)
    
    return {
        "success": True, 
        "message": f"중단 요청됨. 현재 진행: {job['current_row']}/{job['total_rows']}건"
    }
