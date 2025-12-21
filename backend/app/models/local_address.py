from sqlalchemy import Column, Integer, String, Index
from app.db.session import Base

class AddressMaster(Base):
    __tablename__ = "address_master"

    id = Column(Integer, primary_key=True, index=True)
    mgmt_no = Column(String, unique=True, index=True)  # 도로명주소관리번호 (연계키)
    
    # Core Address Fields (Korean)
    si_nm = Column(String, index=True)      # 시도 (서울특별시)
    sgg_nm = Column(String, index=True)     # 시군구 (강남구)
    emd_nm = Column(String, index=True)     # 읍면동 (역삼동)
    
    road_nm = Column(String, index=True)    # 도로명 (테헤란로)
    buld_mainsn = Column(Integer)           # 건물본번 (152)
    buld_subsn = Column(Integer, default=0) # 건물부번 (0)
    
    buld_nm = Column(String, nullable=True, index=True) # 건물명 (강남파이낸스센터)
    zip_no = Column(String)                 # 우편번호 (06236)
    
    # Full Strings for Search (Korean)
    road_full_addr = Column(String)         # 전체 도로명 주소
    jibun_full_addr = Column(String)        # 전체 지번 주소
    
    # English Address Fields
    si_nm_eng = Column(String, nullable=True, index=True)   # Sido (Seoul)
    sgg_nm_eng = Column(String, nullable=True)              # Sigungu (Gangnam-gu)
    road_nm_eng = Column(String, nullable=True, index=True) # Road Name (Teheran-ro)
    road_full_addr_eng = Column(String, nullable=True)      # Full English Address
    
    # Note: Relationship removed for import stability
    # Query detail addresses via mgmt_no join when needed

    # Search Optimization (Index for quick like match)
    __table_args__ = (
        Index('ix_addr_search', 'road_nm', 'buld_mainsn', 'emd_nm'),
        Index('ix_addr_eng_search', 'road_nm_eng', 'buld_mainsn'),
    )


class AddressDetail(Base):
    """상세주소 (동/층/호)"""
    __tablename__ = "address_detail"

    id = Column(Integer, primary_key=True, index=True)
    mgmt_no = Column(String, index=True)  # 연계키 (FK 제거 - Import 안정성)
    
    # Detail Address Fields
    dong = Column(String, nullable=True)       # 동명칭 (101동)
    floor = Column(String, nullable=True)      # 층명칭 (5층)
    ho = Column(String, nullable=True)         # 호명칭 (501호)
    ho_detail = Column(String, nullable=True)  # 호점미사명칭 (A, B)
    is_basement = Column(String, default='0')  # 지하구분 (0:일반, 1:지하)
    
    # Full detail string for display
    detail_full = Column(String, nullable=True)  # 전체 상세주소 문자열
    
    # Note: Relationship removed for import stability
    # Join via mgmt_no when querying
    
    __table_args__ = (
        Index('ix_detail_search', 'mgmt_no', 'dong', 'ho'),
    )


