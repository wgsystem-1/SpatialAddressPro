from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AddressBase(BaseModel):
    raw_text: str

class AddressCreate(AddressBase):
    pass

class AddressResponse(AddressBase):
    id: int
    refined_text: Optional[str] = None
    road_addr: Optional[str] = None
    jibun_addr: Optional[str] = None # Added jibun_addr
    zip_no: Optional[str] = None
    si_nm: Optional[str] = None
    sgg_nm: Optional[str] = None
    emd_nm: Optional[str] = None
    buld_nm: Optional[str] = None
    status: str
    is_ai_corrected: bool = False
    error_message: Optional[str] = None
    candidates: List[dict] = [] # List of potential matches if multiple found
    created_at: datetime

    class Config:
        from_attributes = True

class NormalizationResult(BaseModel):
    """
    Structure for the normalization logic output
    """
    success: bool
    refined_address: Optional[str] = None
    road_address: Optional[str] = None
    jibun_address: Optional[str] = None
    zip_code: Optional[str] = None
    
    si_nm: Optional[str] = None
    sgg_nm: Optional[str] = None
    emd_nm: Optional[str] = None
    buld_nm: Optional[str] = None
    bd_mgt_sn: Optional[str] = None
    bd_mgt_sn: Optional[str] = None
    is_ai_corrected: bool = False
    candidates: List[dict] = []
    
    message: str
