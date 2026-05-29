import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from api.database import engine
from api.models import Base

logger = logging.getLogger("api.main")
logging.basicConfig(level=logging.INFO)

# Initialize Relational Database Tables on startup
try:
    logger.info("Initializing relational application database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Relational tables initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize relational database tables: {e}")

app = FastAPI(
    title="Plag-out Delivery API",
    description="Secure modular REST API for accessing active thermodynamic pest alerts and risk zone predictions, plus GDD simulations.",
    version="1.2.0"
)

# Enable CORS for frontend flexibility (e.g. web views, mapping dashboards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)

