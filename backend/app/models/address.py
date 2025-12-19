from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.db.session import Base

class AddressLog(Base):
    """
    Address Log Model (주소 정제 이력 모델)
    Stores the original input and the refined output.
    """
    __tablename__ = "address_logs"

    id = Column(Integer, primary_key=True, index=True)
    raw_text = Column(Text, nullable=False, comment="Original Input (원본 주소)")
    
    # Refined Results (정제 결과)
    refined_text = Column(String, nullable=True)
    road_addr = Column(String, nullable=True, comment="Road Name Address (도로명 주소)")
    jibun_addr = Column(String, nullable=True, comment="Jibun Address (지번 주소)")
    zip_no = Column(String, nullable=True)
    
    # Detailed Address Components (상세 주소 구성요소)
    si_nm = Column(String, nullable=True, comment="City/Province (시도)")
    sgg_nm = Column(String, nullable=True, comment="District (시군구)")
    emd_nm = Column(String, nullable=True, comment="Town (읍면동)")
    li_nm = Column(String, nullable=True, comment="Village (리)")
    rn = Column(String, nullable=True, comment="Road Name (도로명)")
    buld_nm = Column(String, nullable=True, comment="Building Name (건물명)")
    bd_mgt_sn = Column(String, nullable=True, comment="Building Management No (건물관리번호)")
    
    # Coordinates (If available from API/Geocoding)
    ent_x = Column(String, nullable=True, comment="X Coordinate (GRS80)")
    ent_y = Column(String, nullable=True, comment="Y Coordinate (GRS80)")
    
    ent_y = Column(String, nullable=True, comment="Y Coordinate (GRS80)")
    
    # Status (상태)
    # success, fail, ambiguous
    status = Column(String, default="pending")
    is_ai_corrected = Column(Boolean, default=False, comment="Corrected by LLM?")
    error_message = Column(String, nullable=True, comment="Error Message if failed")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
