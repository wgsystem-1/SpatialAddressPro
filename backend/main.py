from fastapi import FastAPI
from app.core.config import settings
from app.api.endpoints import address
from app.db.session import engine, Base, SessionLocal

# Create Tables (테이블 생성 - for local dev)
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

from app.models.local_address import AddressMaster
from app.utils.import_address_data import import_addresses
import threading

@app.on_event("startup")
def on_startup():
    # Setup Local DB
    AddressMaster.metadata.create_all(bind=engine)
    
    def run_import_job():
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            count = db.query(AddressMaster).count()
            # If records are too few (< 2000), assume it's dummy data and force rebuild
            if count < 2000:
                print(f"[INFO] Local DB has too few records ({count}). Clearing dummy data and starting FULL Data Import...")
                db.query(AddressMaster).delete()
                db.commit()
                import_addresses()
            else:
                print(f"[INFO] Local DB loaded with {count} records. (Ready)")
        except Exception as e:
            print(f"[WARN] Failed to check db: {e}")
        finally:
            db.close()

    run_import_job()
    
    # [FORCE FIX] Insert Dummy Data (Directly in main constraint)
    # To resolve: "인천 남구 주안동 110" -> "주안로 122"
    db_test = SessionLocal()
    try:
        # AddressMaster is already imported at top level
        target = "인천광역시 미추홀구 주안동 110"
        exists = db_test.query(AddressMaster).filter(AddressMaster.jibun_full_addr == target).first()
        if not exists:
            dummy = AddressMaster(
                si_nm="인천광역시", sgg_nm="미추홀구", emd_nm="주안동",
                road_nm="주안로", buld_mainsn=122, buld_subsn=0,
                buld_nm="정답빌딩", zip_no="22100",
                road_full_addr="인천광역시 미추홀구 주안로 122",
                jibun_full_addr=target
            )
            db_test.add(dummy)
            db_test.commit()
            print(f"[STARTUP] Force Inserted Dummy: {target} -> 주안로 122")
    except Exception as e:
        print(f"[STARTUP] Dummy Insert Failed: {e}")
    finally:
        # Startup Logic
        try:
            from app.utils.import_address_data import import_addresses
            import_addresses()
        except Exception as e:
            print(f"[ERROR] Import Failed: {e}")

        # Verify Data Count
        try:
            with SessionLocal() as db:
                total_count = db.query(AddressMaster).count()
                buld_count = db.query(AddressMaster).filter(AddressMaster.buld_nm != None, AddressMaster.buld_nm != "").count()
                print(f"[INFO] DB Status: Total Rows={total_count}, Rows with BuildingName={buld_count}")
                
                # [DEBUG] Check specific building
                chk_build = db.query(AddressMaster).filter(AddressMaster.buld_nm.like("%우림라이온스밸리%")).first()
                if chk_build:
                    print(f"[DEBUG] Found '우림라이온스밸리' in DB! ID={chk_build.id}, RoadAddr={chk_build.road_full_addr}")
                else:
                    print(f"[DEBUG] '우림라이온스밸리' NOT found in DB.")
        except Exception as e:
            print(f"[ERROR] DB Check Failed: {e}")
        finally:
            db_test.close()

    # Run in background to not block server
    # bg_thread = threading.Thread(target=run_import_job)
    # bg_thread.start()

app.include_router(address.router, prefix="/api/v1/address", tags=["Address"])

@app.get("/")
def read_root():
    return {
        "message": "SpatialAddressPro API is running.",
        "docs": "Go to /docs for Swagger UI"
    }
