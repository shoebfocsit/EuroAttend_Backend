from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "EmployeeAttendance"
    APP_TZ: str = "Asia/Kolkata"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DATABASE_URL: str = "sqlite:///./dev.db"

    ADMIN_NAME: str = "Administrator"
    ADMIN_MOBILE: str = "9999999999"
    ADMIN_PASSWORD: str = "Admin@123"

    SHIFT_START: str = "10:00"
    SHIFT_END: str = "19:00"
    LATE_AFTER_MINUTES: int = 15
    HALF_DAY_HOURS: float = 4.0
    MIN_SHIFT_HOURS: float = 8.0
    MAX_BREAK_MINUTES: int = 45
    MAX_GPS_ACCURACY_M: float = 200
    OVERTIME_ALLOWED: bool = True
    OVERTIME_LIMIT_HOURS: float = 3.0
    LUNCH_REMINDER_AT: str = "13:00"
    AUTO_PUNCHOUT_ENABLED: bool = True

    GEOFENCE_LAT: float = 28.6139
    GEOFENCE_LNG: float = 77.2090
    GEOFENCE_RADIUS_M: float = 500
    STRICT_GEOFENCE: bool = False
    STRICT_MOCK_BLOCK: bool = False

    TRACK_INTERVAL_SEC: int = 90
    TRACK_MIN_DISTANCE_M: int = 50

    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "./uploads"

    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
