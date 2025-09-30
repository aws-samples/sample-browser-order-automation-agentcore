#!/usr/bin/env python3
"""
SQLAlchemy-based database models and management for order automation system
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    DateTime,
    Text,
    text,
    JSON,
    BigInteger,
    Float,
    Boolean,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func, and_, or_
import uuid

logger = logging.getLogger(__name__)

Base = declarative_base()


class OrderStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_HUMAN = "requires_human"
    MANUAL_CONTROL = "manual_control"


class OrderPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class AutomationMethod(Enum):
    NOVA_ACT = "nova_act"
    STRANDS = "strands"


class OrderModel(Base):
    """SQLAlchemy Order model"""

    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    retailer = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    priority = Column(Integer, nullable=False)
    automation_method = Column(String(50), nullable=False)
    ai_model = Column(String(200))  # AI model used for automation

    # Product information
    product_name = Column(String(500), nullable=False)
    product_url = Column(Text, nullable=False)
    product_size = Column(String(50))
    product_color = Column(String(100))
    product_price = Column(Float)

    # Customer information
    customer_name = Column(String(200), nullable=False)
    customer_email = Column(String(200), nullable=False)

    # Shipping address
    shipping_address = Column(JSON, nullable=False)

    # Payment information (tokenized)
    payment_token = Column(String(500))

    # Order tracking
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    progress = Column(Integer, default=0)
    current_step = Column(String(200))

    # Results
    order_confirmation_number = Column(String(100))
    tracking_number = Column(String(100))
    estimated_delivery = Column(DateTime)

    # Error handling
    error_message = Column(Text)
    requires_human_review = Column(Boolean, default=False)
    human_review_notes = Column(Text)

    # Automation metadata
    session_id = Column(String(100))
    automation_metadata = Column("metadata", JSON)
    execution_logs = Column(JSON)
    screenshots = Column(JSON)

    # Session replay
    session_replay_s3_bucket = Column(String(200))
    session_replay_s3_prefix = Column(String(500))
    session_replay_enabled = Column(Boolean, default=False)


class SessionModel(Base):
    """SQLAlchemy Browser Session model"""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    automation_method = Column(String(50), nullable=False)
    status = Column(
        String(20), nullable=False
    )  # active, processing, completed, terminated
    retailer = Column(String(100))
    current_url = Column(Text)
    thumbnail_url = Column(Text)

    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    terminated_at = Column(DateTime)

    session_metadata = Column("metadata", JSON)


class SettingsModel(Base):
    """SQLAlchemy Settings model"""

    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RetailerUrlModel(Base):
    """SQLAlchemy Retailer URL mapping model"""

    __tablename__ = "retailer_urls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    retailer = Column(String(100), nullable=False)
    website_name = Column(String(200), nullable=False)
    starting_url = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SecretVaultModel(Base):
    """SQLAlchemy Secret Vault model for storing site credentials"""

    __tablename__ = "secret_vault"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    site_name = Column(String, nullable=False)  # e.g., "amazon", "ebay"
    site_url = Column(String, nullable=False)   # e.g., "https://amazon.com"
    username = Column(String, nullable=True)    # Encrypted username/email
    password = Column(String, nullable=True)    # Encrypted password
    additional_fields = Column(JSON, nullable=True)  # Other fields like security questions
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


@dataclass
class Order:
    """Order dataclass for API responses"""

    id: str
    retailer: str
    status: OrderStatus
    priority: OrderPriority
    automation_method: AutomationMethod
    product_name: str
    product_url: str
    customer_name: str
    customer_email: str

    # Optional fields with defaults
    ai_model: Optional[str] = None
    product_size: Optional[str] = None
    product_color: Optional[str] = None
    product_price: Optional[float] = None
    shipping_address: Optional[Dict[str, Any]] = None
    payment_token: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    current_step: Optional[str] = None
    order_confirmation_number: Optional[str] = None
    tracking_number: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    error_message: Optional[str] = None
    requires_human_review: bool = False
    human_review_notes: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution_logs: Optional[List[Dict[str, Any]]] = None
    screenshots: Optional[List[Dict[str, Any]]] = None
    session_replay_s3_bucket: Optional[str] = None
    session_replay_s3_prefix: Optional[str] = None
    session_replay_enabled: bool = False

    def to_dict(self):
        data = asdict(self)
        # Convert datetime objects to ISO strings with UTC timezone
        for field in [
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "estimated_delivery",
        ]:
            if data[field]:
                dt = data[field]
                # Ensure datetime is timezone-aware (assume UTC if naive)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                data[field] = dt.isoformat()
        # Convert enums to values
        data["status"] = (
            self.status.value if hasattr(self.status, "value") else self.status
        )
        data["priority"] = (
            self.priority.value if hasattr(self.priority, "value") else self.priority
        )
        data["automation_method"] = (
            self.automation_method.value
            if hasattr(self.automation_method, "value")
            else self.automation_method
        )

        # Add display name for automation method
        method_display_names = {
            "nova_act": "Nova Act + AgentCore Browser",
            "strands": "Strands + AgentCore Browser + Browser Tools",
        }
        data["automation_method_display"] = method_display_names.get(
            data["automation_method"], data["automation_method"]
        )

        # Add product object for frontend compatibility
        data["product"] = {
            "name": data.get("product_name") or "-",
            "url": data.get("product_url") or "-",
            "size": data.get("product_size") or "-",  # Replace None with "-"
            "color": data.get("product_color") or "-",  # Replace None with "-"
            "price": data.get("product_price"),
            "quantity": 1,  # Default quantity
        }

        # Add status tooltip for failed orders
        if data["status"] == "failed" and data.get("error_message"):
            data["status_tooltip"] = data["error_message"]
        elif data["status"] == "failed":
            data["status_tooltip"] = "Order processing failed"
        else:
            data["status_tooltip"] = None

        # Ensure execution_logs and screenshots are included
        data["execution_logs"] = self.execution_logs or []
        data["screenshots"] = self.screenshots or []

        # Clean up None values and replace with "-" for display (except specific fields)
        for key, value in data.items():
            if value is None and key not in [
                "completed_at",
                "started_at",
                "estimated_delivery",
                "product_price",
                "status_tooltip",
                "execution_logs",
                "screenshots",
            ]:
                data[key] = "-"

        return data


@dataclass
class BrowserSession:
    """Browser Session dataclass for API responses"""

    id: str
    automation_method: AutomationMethod
    status: str
    retailer: Optional[str] = None
    current_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self):
        data = asdict(self)
        # Convert datetime objects to ISO strings with UTC timezone
        for field in ["created_at", "updated_at", "terminated_at"]:
            if data[field]:
                dt = data[field]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                data[field] = dt.isoformat()
        # Convert enums to values
        data["automation_method"] = (
            self.automation_method.value
            if hasattr(self.automation_method, "value")
            else self.automation_method
        )
        return data


@dataclass
class SecretVault:
    """Secret Vault dataclass for API responses"""

    id: str
    site_name: str
    site_url: str
    username: Optional[str] = None
    password: Optional[str] = None  # This will be masked in API responses
    additional_fields: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self, include_password: bool = False):
        data = asdict(self)
        # Convert datetime objects to ISO strings with UTC timezone
        for field in ["created_at", "updated_at"]:
            if data[field]:
                dt = data[field]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                data[field] = dt.isoformat()
        
        # Mask password unless explicitly requested
        if not include_password and data.get("password"):
            data["password"] = "***masked***"
        
        return data


class DatabaseManager:
    """SQLAlchemy-based database manager for order automation system"""

    def __init__(self, db_url: str = None):
        if not db_url:
            # Check for environment-specific database URL
            if os.getenv("ENVIRONMENT") == "production":
                # Use RDS in production
                db_url = os.getenv("DATABASE_URL")
                if not db_url:
                    raise ValueError(
                        "DATABASE_URL environment variable required for production"
                    )
            else:
                # Use SQLite locally
                db_path = os.path.join(os.path.dirname(__file__), "order_automation.db")
                db_url = f"sqlite:///{db_path}"

        self.engine = create_engine(
            db_url,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,  # Verify connections before use
        )

        # Create tables
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Log database type and set compatibility flag
        self.use_postgres = "postgresql" in db_url.lower()
        if self.use_postgres:
            logger.info("Using PostgreSQL database (RDS)")
        else:
            logger.info("Using SQLite database (local)")

        # Run database migrations
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations"""
        try:
            with self.get_session() as session:
                # Migration 1: Check if ai_model column exists
                if not self.use_postgres:
                    # SQLite migration
                    try:
                        session.execute(text("SELECT ai_model FROM orders LIMIT 1"))
                        logger.info("ai_model column already exists")
                    except Exception:
                        logger.info("Adding ai_model column to orders table")
                        session.execute(
                            text("ALTER TABLE orders ADD COLUMN ai_model VARCHAR(200)")
                        )
                        session.commit()
                        logger.info("Successfully added ai_model column")
                else:
                    # PostgreSQL migration
                    try:
                        session.execute(text("SELECT ai_model FROM orders LIMIT 1"))
                        logger.info("ai_model column already exists")
                    except Exception:
                        logger.info("Adding ai_model column to orders table")
                        session.execute(
                            text("ALTER TABLE orders ADD COLUMN ai_model VARCHAR(200)")
                        )
                        session.commit()
                        logger.info("Successfully added ai_model column")

                # Migration 2: Update old automation method values
                try:
                    logger.info("Updating old automation method values")
                    # Update old values to new ones
                    session.execute(
                        text(
                            "UPDATE orders SET automation_method = 'strands' WHERE automation_method = 'strands_browser'"
                        )
                    )
                    session.execute(
                        text(
                            "UPDATE orders SET automation_method = 'strands' WHERE automation_method = 'strands_playwright_mcp'"
                        )
                    )
                    session.execute(
                        text(
                            "UPDATE orders SET automation_method = 'strands' WHERE automation_method = 'strands_unified'"
                        )
                    )
                    session.commit()
                    logger.info("Successfully updated automation method values")
                except Exception as e:
                    logger.warning(f"Failed to update automation method values: {e}")

                # Migration 3: Initialize default retailer URLs
                try:
                    self.initialize_default_retailer_urls()
                except Exception as e:
                    logger.warning(f"Failed to initialize default retailer URLs: {e}")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            # Don't raise exception to allow system to continue

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()

    def create_order(
        self,
        retailer: str,
        automation_method: AutomationMethod,
        product_name: str,
        product_url: str,
        customer_name: str,
        customer_email: str,
        shipping_address: Dict[str, Any],
        ai_model: Optional[str] = None,
        product_size: Optional[str] = None,
        product_color: Optional[str] = None,
        product_price: Optional[float] = None,
        payment_token: Optional[str] = None,
        priority: OrderPriority = OrderPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        instructions: Optional[str] = None,
    ) -> str:
        """Create a new order"""
        try:
            # Prepare metadata with instructions
            if metadata is None:
                metadata = {}
            if instructions:
                metadata["instructions"] = instructions

            with self.get_session() as session:
                order = OrderModel(
                    retailer=retailer,
                    status=OrderStatus.PENDING.value,
                    priority=priority.value,
                    automation_method=automation_method.value,
                    ai_model=ai_model,
                    product_name=product_name,
                    product_url=product_url,
                    product_size=product_size,
                    product_color=product_color,
                    product_price=product_price,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    shipping_address=shipping_address,
                    payment_token=payment_token,
                    automation_metadata=metadata,
                )
                session.add(order)
                session.commit()

                logger.info(f"Created order {order.id}: {retailer} - {product_name}")
                return order.id
        except Exception as e:
            logger.error(f"DatabaseManager.create_order() failed: {e}")
            raise

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        try:
            with self.get_session() as session:
                order_model = (
                    session.query(OrderModel).filter(OrderModel.id == order_id).first()
                )
                return self._model_to_order(order_model) if order_model else None
        except Exception as e:
            logger.error(f"DatabaseManager.get_order({order_id}) failed: {e}")
            raise

    def get_all_orders(
        self,
        status_filter: List[str] = None,
        retailer_filter: str = None,
    ) -> List[Order]:
        """Get all orders with optional filtering"""
        try:
            with self.get_session() as session:
                query = session.query(OrderModel)

                if status_filter:
                    query = query.filter(OrderModel.status.in_(status_filter))

                if retailer_filter:
                    query = query.filter(OrderModel.retailer == retailer_filter)

                query = query.order_by(OrderModel.created_at.desc())
                order_models = query.all()

                return [
                    self._model_to_order(order_model) for order_model in order_models
                ]
        except Exception as e:
            logger.error(f"DatabaseManager.get_all_orders() failed: {e}")
            logger.error(f"Parameters: status_filter={status_filter}, retailer_filter={retailer_filter}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []

    def get_orders_requiring_human_review(self) -> List[Order]:
        """Get orders that require human review based on the requires_human_review flag"""
        try:
            with self.get_session() as session:
                order_models = (
                    session.query(OrderModel)
                    .filter(OrderModel.requires_human_review == True)
                    .order_by(OrderModel.created_at.desc())
                    .all()
                )

                return [
                    self._model_to_order(order_model) for order_model in order_models
                ]
        except Exception as e:
            logger.error(f"DatabaseManager.get_orders_requiring_human_review() failed: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []

    def get_next_order(self) -> Optional[Order]:
        """Get next pending order by priority and atomically mark it as processing"""
        try:
            with self.get_session() as session:
                # Find and update in one transaction
                order_model = (
                    session.query(OrderModel)
                    .filter(OrderModel.status == OrderStatus.PENDING.value)
                    .order_by(OrderModel.priority.desc(), OrderModel.created_at.asc())
                    .with_for_update(
                        skip_locked=True
                    )  # PostgreSQL skip locked, SQLite will ignore
                    .first()
                )

                if order_model:
                    now = datetime.now(timezone.utc)
                    order_model.status = OrderStatus.PROCESSING.value
                    order_model.updated_at = now
                    order_model.started_at = now
                    session.commit()

                    return self._model_to_order(order_model)

                return None
        except Exception as e:
            logger.error(f"DatabaseManager.get_next_order() failed: {e}")
            raise

    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        order_confirmation_number: Optional[str] = None,
        tracking_number: Optional[str] = None,
        estimated_delivery: Optional[datetime] = None,
        error_message: Optional[str] = None,
        requires_human_review: Optional[bool] = None,
        session_id: Optional[str] = None,
    ):
        """Update order status and related fields"""
        try:
            with self.get_session() as session:
                order_model = (
                    session.query(OrderModel).filter(OrderModel.id == order_id).first()
                )

                if not order_model:
                    raise ValueError(f"Order {order_id} not found")

                now = datetime.now(timezone.utc)
                order_model.status = status.value
                order_model.updated_at = now

                if progress is not None:
                    order_model.progress = progress

                if current_step is not None:
                    order_model.current_step = current_step

                if order_confirmation_number is not None:
                    order_model.order_confirmation_number = order_confirmation_number

                if tracking_number is not None:
                    order_model.tracking_number = tracking_number

                if estimated_delivery is not None:
                    order_model.estimated_delivery = estimated_delivery

                if error_message is not None:
                    order_model.error_message = error_message

                if requires_human_review is not None:
                    order_model.requires_human_review = requires_human_review

                if session_id is not None:
                    order_model.session_id = session_id

                # Set timestamps based on status
                if status == OrderStatus.PROCESSING and not order_model.started_at:
                    order_model.started_at = now
                elif status in [
                    OrderStatus.COMPLETED,
                    OrderStatus.FAILED,
                    OrderStatus.CANCELLED,
                ]:
                    order_model.completed_at = now

                session.commit()
        except Exception as e:
            logger.error(f"DatabaseManager.update_order_status({order_id}) failed: {e}")
            raise

    def add_execution_log(
        self, order_id: str, level: str, message: str, step: Optional[str] = None
    ):
        """Add execution log entry to order"""
        try:
            with self.get_session() as session:
                order_model = (
                    session.query(OrderModel).filter(OrderModel.id == order_id).first()
                )

                if not order_model:
                    raise ValueError(f"Order {order_id} not found")

                # Initialize execution_logs if None
                if order_model.execution_logs is None:
                    order_model.execution_logs = []

                # Create log entry
                log_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": level,
                    "message": message,
                    "step": step,
                }

                # Add to logs (create new list to trigger SQLAlchemy update)
                logs = list(order_model.execution_logs)
                logs.append(log_entry)
                order_model.execution_logs = logs
                order_model.updated_at = datetime.now(timezone.utc)

                session.commit()
                logger.debug(
                    f"Added execution log to order {order_id}: {level} - {message}"
                )

        except Exception as e:
            logger.error(f"DatabaseManager.add_execution_log({order_id}) failed: {e}")
            raise

    def add_screenshot(
        self,
        order_id: str,
        screenshot_url: str,
        step: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Add screenshot to order"""
        try:
            with self.get_session() as session:
                order_model = (
                    session.query(OrderModel).filter(OrderModel.id == order_id).first()
                )

                if not order_model:
                    raise ValueError(f"Order {order_id} not found")

                # Initialize screenshots if None
                if order_model.screenshots is None:
                    order_model.screenshots = []

                # Create screenshot entry
                screenshot_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "url": screenshot_url,
                    "step": step,
                    "description": description,
                }

                # Add to screenshots (create new list to trigger SQLAlchemy update)
                screenshots = list(order_model.screenshots)
                screenshots.append(screenshot_entry)
                order_model.screenshots = screenshots
                order_model.updated_at = datetime.now(timezone.utc)

                session.commit()
                logger.debug(f"Added screenshot to order {order_id}: {screenshot_url}")

        except Exception as e:
            logger.error(f"DatabaseManager.add_screenshot({order_id}) failed: {e}")
            raise

    def update_session_replay_info(
        self,
        order_id: str,
        s3_bucket: str,
        s3_prefix: str,
        enabled: bool = True,
        session_id: str = None,
    ):
        """Update session replay information for an order"""
        try:
            with self.get_session() as session:
                order_model = (
                    session.query(OrderModel).filter(OrderModel.id == order_id).first()
                )
                if not order_model:
                    raise ValueError(f"Order {order_id} not found")

                order_model.session_replay_s3_bucket = s3_bucket
                order_model.session_replay_s3_prefix = s3_prefix
                order_model.session_replay_enabled = enabled
                if session_id:
                    order_model.session_id = session_id
                order_model.updated_at = datetime.now(timezone.utc)

                session.commit()
                logger.debug(
                    f"Updated session replay info for order {order_id}: {s3_bucket}/{s3_prefix}"
                )

        except Exception as e:
            logger.error(
                f"DatabaseManager.update_session_replay_info({order_id}) failed: {e}"
            )
            raise

    def get_session_replay_info(self, order_id: str) -> Dict[str, Any]:
        """Get session replay information for an order"""
        try:
            with self.get_session() as session:
                order_model = (
                    session.query(OrderModel).filter(OrderModel.id == order_id).first()
                )
                if not order_model:
                    raise ValueError(f"Order {order_id} not found")

                return {
                    "s3_bucket": order_model.session_replay_s3_bucket,
                    "s3_prefix": order_model.session_replay_s3_prefix,
                    "enabled": order_model.session_replay_enabled or False,
                    "session_id": order_model.session_id,
                }

        except Exception as e:
            logger.error(
                f"DatabaseManager.get_session_replay_info({order_id}) failed: {e}"
            )
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        try:
            with self.get_session() as session:
                result = (
                    session.query(OrderModel)
                    .filter(
                        and_(
                            OrderModel.id == order_id,
                            OrderModel.status == OrderStatus.PENDING.value,
                        )
                    )
                    .update(
                        {
                            "status": OrderStatus.CANCELLED.value,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                )
                session.commit()
                return result > 0
        except Exception as e:
            logger.error(f"DatabaseManager.cancel_order({order_id}) failed: {e}")
            raise

    def delete_order(self, order_id: str) -> bool:
        """Delete an order from database"""
        try:
            with self.get_session() as session:
                result = (
                    session.query(OrderModel).filter(OrderModel.id == order_id).delete()
                )
                session.commit()
                return result > 0
        except Exception as e:
            logger.error(f"DatabaseManager.delete_order({order_id}) failed: {e}")
            raise

    # Browser Session Management
    def create_session(
        self,
        automation_method: AutomationMethod,
        retailer: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new browser session"""
        try:
            with self.get_session() as session:
                browser_session = SessionModel(
                    automation_method=automation_method.value,
                    status="active",
                    retailer=retailer,
                    session_metadata=metadata,
                )
                session.add(browser_session)
                session.commit()

                logger.info(
                    f"Created browser session {browser_session.id}: {automation_method.value}"
                )
                return browser_session.id
        except Exception as e:
            logger.error(f"DatabaseManager.create_session() failed: {e}")
            raise

    def get_browser_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get browser session by ID"""
        try:
            with self.get_session() as db_session:
                session_model = (
                    db_session.query(SessionModel)
                    .filter(SessionModel.id == session_id)
                    .first()
                )
                return self._model_to_session(session_model) if session_model else None
        except Exception as e:
            logger.error(
                f"DatabaseManager.get_browser_session({session_id}) failed: {e}"
            )
            raise

    def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        current_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
    ):
        """Update browser session"""
        try:
            with self.get_session() as db_session:
                session_model = (
                    db_session.query(SessionModel)
                    .filter(SessionModel.id == session_id)
                    .first()
                )

                if not session_model:
                    raise ValueError(f"Session {session_id} not found")

                now = datetime.now(timezone.utc)
                session_model.updated_at = now

                if status is not None:
                    session_model.status = status
                    if status == "terminated":
                        session_model.terminated_at = now

                if current_url is not None:
                    session_model.current_url = current_url

                if thumbnail_url is not None:
                    session_model.thumbnail_url = thumbnail_url

                db_session.commit()
        except Exception as e:
            logger.error(f"DatabaseManager.update_session({session_id}) failed: {e}")
            raise

    def get_all_sessions(self, limit: int = 50) -> List[BrowserSession]:
        """Get all browser sessions"""
        try:
            with self.get_session() as db_session:
                session_models = (
                    db_session.query(SessionModel)
                    .order_by(SessionModel.created_at.desc())
                    .limit(limit)
                    .all()
                )

                return [
                    self._model_to_session(session_model)
                    for session_model in session_models
                ]
        except Exception as e:
            logger.error(f"DatabaseManager.get_all_sessions() failed: {e}")
            return []

    def get_order_stats(self) -> Dict[str, Any]:
        """Get order statistics and metrics"""
        try:
            with self.get_session() as session:
                # Basic status counts
                status_counts = (
                    session.query(OrderModel.status, func.count(OrderModel.id))
                    .group_by(OrderModel.status)
                    .all()
                )

                stats = {status.value: 0 for status in OrderStatus}
                for status, count in status_counts:
                    stats[status] = count

                # Human review queue count
                review_count = (
                    session.query(func.count(OrderModel.id))
                    .filter(OrderModel.requires_human_review == True)
                    .scalar()
                    or 0
                )
                stats["review_queue"] = review_count

                # Calculate total orders
                stats["total_orders"] = sum(
                    stats[status.value] for status in OrderStatus
                )

                # Calculate average processing time for completed orders
                completed_orders_with_times = (
                    session.query(OrderModel.started_at, OrderModel.completed_at)
                    .filter(
                        and_(
                            OrderModel.status == OrderStatus.COMPLETED.value,
                            OrderModel.started_at.isnot(None),
                            OrderModel.completed_at.isnot(None),
                        )
                    )
                    .all()
                )

                if completed_orders_with_times:
                    total_time = 0
                    valid_orders = 0
                    for started_at, completed_at in completed_orders_with_times:
                        if started_at and completed_at and completed_at > started_at:
                            duration = (completed_at - started_at).total_seconds()
                            # Filter out unreasonably long durations (more than 2 hours)
                            if (
                                0 < duration <= 7200
                            ):  # Only count durations between 0 and 2 hours
                                total_time += duration
                                valid_orders += 1
                            elif duration > 7200:
                                logger.warning(
                                    f"Excluding abnormally long order duration: {duration}s"
                                )

                    avg_time = total_time / valid_orders if valid_orders > 0 else 0
                else:
                    avg_time = 0

                stats["avg_processing_time"] = round(avg_time, 2)

                # Success rate
                total_finished = stats["completed"] + stats["failed"]
                stats["success_rate"] = (
                    (stats["completed"] / total_finished * 100)
                    if total_finished > 0
                    else 0
                )

                # Orders created today
                today_count = (
                    session.query(func.count(OrderModel.id))
                    .filter(func.date(OrderModel.created_at) == func.current_date())
                    .scalar()
                    or 0
                )
                stats["orders_today"] = today_count

                # Retailer breakdown
                retailer_counts = (
                    session.query(OrderModel.retailer, func.count(OrderModel.id))
                    .group_by(OrderModel.retailer)
                    .all()
                )
                stats["retailer_breakdown"] = {
                    retailer: count for retailer, count in retailer_counts
                }

                # Automation method breakdown
                method_counts = (
                    session.query(
                        OrderModel.automation_method, func.count(OrderModel.id)
                    )
                    .group_by(OrderModel.automation_method)
                    .all()
                )
                stats["automation_method_breakdown"] = {
                    method: count for method, count in method_counts
                }

                return stats
        except Exception as e:
            logger.error(f"DatabaseManager.get_order_stats() failed: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Return empty stats instead of crashing
            return {status.value: 0 for status in OrderStatus}

    def cleanup_old_orders(self, days: int = 30):
        """Clean up old completed orders"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            with self.get_session() as session:
                result = (
                    session.query(OrderModel)
                    .filter(
                        and_(
                            OrderModel.status.in_(
                                [
                                    OrderStatus.COMPLETED.value,
                                    OrderStatus.FAILED.value,
                                    OrderStatus.CANCELLED.value,
                                ]
                            ),
                            OrderModel.completed_at < cutoff_date,
                        )
                    )
                    .delete()
                )
                session.commit()

                logger.info(f"Cleaned up {result} old orders")
                return result
        except Exception as e:
            logger.error(f"DatabaseManager.cleanup_old_orders() failed: {e}")
            raise

    def delete_completed_orders(self) -> int:
        """Delete all completed and failed orders"""
        try:
            with self.get_session() as session:
                result = (
                    session.query(OrderModel)
                    .filter(
                        OrderModel.status.in_(
                            [OrderStatus.COMPLETED.value, OrderStatus.FAILED.value]
                        )
                    )
                    .delete(synchronize_session=False)
                )
                session.commit()

                logger.info(f"Deleted {result} completed and failed orders")
                return result
        except Exception as e:
            logger.error(f"DatabaseManager.delete_completed_orders() failed: {e}")
            raise

    def cleanup_old_sessions(self, days: int = 7):
        """Clean up old terminated sessions"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            with self.get_session() as session:
                result = (
                    session.query(SessionModel)
                    .filter(
                        and_(
                            SessionModel.status == "terminated",
                            SessionModel.terminated_at < cutoff_date,
                        )
                    )
                    .delete()
                )
                session.commit()

                logger.info(f"Cleaned up {result} old sessions")
                return result
        except Exception as e:
            logger.error(f"DatabaseManager.cleanup_old_sessions() failed: {e}")
            raise

    def _model_to_order(self, order_model: OrderModel) -> Order:
        """Convert SQLAlchemy model to Order dataclass"""
        return Order(
            id=order_model.id,
            retailer=order_model.retailer,
            status=OrderStatus(order_model.status),
            priority=OrderPriority(order_model.priority),
            automation_method=AutomationMethod(order_model.automation_method),
            ai_model=order_model.ai_model,
            product_name=order_model.product_name,
            product_url=order_model.product_url,
            product_size=order_model.product_size,
            product_color=order_model.product_color,
            product_price=order_model.product_price,
            customer_name=order_model.customer_name,
            customer_email=order_model.customer_email,
            shipping_address=order_model.shipping_address,
            payment_token=order_model.payment_token,
            created_at=order_model.created_at,
            updated_at=order_model.updated_at,
            started_at=order_model.started_at,
            completed_at=order_model.completed_at,
            progress=order_model.progress,
            current_step=order_model.current_step,
            order_confirmation_number=order_model.order_confirmation_number,
            tracking_number=order_model.tracking_number,
            estimated_delivery=order_model.estimated_delivery,
            error_message=order_model.error_message,
            requires_human_review=order_model.requires_human_review,
            human_review_notes=order_model.human_review_notes,
            session_id=order_model.session_id,
            metadata=order_model.automation_metadata,
            execution_logs=order_model.execution_logs or [],
            screenshots=order_model.screenshots or [],
        )

    def _model_to_session(self, session_model: SessionModel) -> BrowserSession:
        """Convert SQLAlchemy model to BrowserSession dataclass"""
        return BrowserSession(
            id=session_model.id,
            automation_method=AutomationMethod(session_model.automation_method),
            status=session_model.status,
            retailer=session_model.retailer,
            current_url=session_model.current_url,
            thumbnail_url=session_model.thumbnail_url,
            created_at=session_model.created_at,
            updated_at=session_model.updated_at,
            terminated_at=session_model.terminated_at,
            metadata=session_model.session_metadata,
        )

    # Settings management
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        try:
            with self.get_session() as session:
                setting = (
                    session.query(SettingsModel)
                    .filter(SettingsModel.key == key)
                    .first()
                )
                return setting.value if setting else default
        except Exception as e:
            logger.error(f"DatabaseManager.get_setting({key}) failed: {e}")
            return default

    def set_setting(self, key: str, value: Any):
        """Set a setting value"""
        try:
            with self.get_session() as session:
                setting = (
                    session.query(SettingsModel)
                    .filter(SettingsModel.key == key)
                    .first()
                )

                if setting:
                    setting.value = value
                    setting.updated_at = datetime.now(timezone.utc)
                else:
                    setting = SettingsModel(key=key, value=value)
                    session.add(setting)

                session.commit()
        except Exception as e:
            logger.error(f"DatabaseManager.set_setting({key}) failed: {e}")
            raise

    def close(self):
        """Close database connections"""
        try:
            if hasattr(self, 'engine') and self.engine:
                self.engine.dispose()
                logger.info("Database engine disposed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings"""
        try:
            with self.get_session() as session:
                settings = session.query(SettingsModel).all()
                return {setting.key: setting.value for setting in settings}
        except Exception as e:
            logger.error(f"DatabaseManager.get_all_settings() failed: {e}")
            return {}

    def update_multiple_settings(self, settings: Dict[str, Any]):
        """Update multiple settings atomically"""
        try:
            with self.get_session() as session:
                for key, value in settings.items():
                    setting = (
                        session.query(SettingsModel)
                        .filter(SettingsModel.key == key)
                        .first()
                    )

                    if setting:
                        setting.value = value
                        setting.updated_at = datetime.now(timezone.utc)
                    else:
                        setting = SettingsModel(key=key, value=value)
                        session.add(setting)

                session.commit()
                logger.info(f"Updated {len(settings)} settings atomically")
        except Exception as e:
            logger.error(f"DatabaseManager.update_multiple_settings() failed: {e}")
            raise

    # Retailer URL Management
    def get_retailer_urls(self, retailer: str = None) -> List[Dict[str, Any]]:
        """Get retailer URL mappings"""
        try:
            with self.get_session() as session:
                query = session.query(RetailerUrlModel).filter(RetailerUrlModel.is_active == True)
                if retailer:
                    query = query.filter(RetailerUrlModel.retailer == retailer)
                
                urls = query.order_by(RetailerUrlModel.is_default.desc(), RetailerUrlModel.created_at).all()
                return [
                    {
                        "id": url.id,
                        "retailer": url.retailer,
                        "website_name": url.website_name,
                        "starting_url": url.starting_url,
                        "is_default": url.is_default,
                        "is_active": url.is_active,
                        "created_at": url.created_at.isoformat(),
                        "updated_at": url.updated_at.isoformat(),
                    }
                    for url in urls
                ]
        except Exception as e:
            logger.error(f"DatabaseManager.get_retailer_urls({retailer}) failed: {e}")
            return []

    def add_retailer_url(self, retailer: str, website_name: str, starting_url: str, is_default: bool = False) -> str:
        """Add a new retailer URL mapping"""
        try:
            with self.get_session() as session:
                # If this is set as default, unset other defaults for this retailer
                if is_default:
                    session.query(RetailerUrlModel).filter(
                        RetailerUrlModel.retailer == retailer,
                        RetailerUrlModel.is_default == True
                    ).update({"is_default": False})

                url_mapping = RetailerUrlModel(
                    retailer=retailer,
                    website_name=website_name,
                    starting_url=starting_url,
                    is_default=is_default
                )
                session.add(url_mapping)
                session.commit()
                
                logger.info(f"Added retailer URL mapping: {retailer} -> {website_name}")
                return url_mapping.id
        except Exception as e:
            logger.error(f"DatabaseManager.add_retailer_url() failed: {e}")
            raise

    def update_retailer_url(self, url_id: str, **kwargs) -> bool:
        """Update a retailer URL mapping"""
        try:
            with self.get_session() as session:
                url_mapping = session.query(RetailerUrlModel).filter(RetailerUrlModel.id == url_id).first()
                if not url_mapping:
                    return False

                # If setting as default, unset other defaults for this retailer
                if kwargs.get("is_default"):
                    session.query(RetailerUrlModel).filter(
                        RetailerUrlModel.retailer == url_mapping.retailer,
                        RetailerUrlModel.is_default == True,
                        RetailerUrlModel.id != url_id
                    ).update({"is_default": False})

                # Update fields
                for key, value in kwargs.items():
                    if hasattr(url_mapping, key):
                        setattr(url_mapping, key, value)
                
                url_mapping.updated_at = datetime.now(timezone.utc)
                session.commit()
                
                logger.info(f"Updated retailer URL mapping: {url_id}")
                return True
        except Exception as e:
            logger.error(f"DatabaseManager.update_retailer_url({url_id}) failed: {e}")
            return False

    def delete_retailer_url(self, url_id: str) -> bool:
        """Delete a retailer URL mapping (soft delete)"""
        try:
            with self.get_session() as session:
                url_mapping = session.query(RetailerUrlModel).filter(RetailerUrlModel.id == url_id).first()
                if not url_mapping:
                    return False

                url_mapping.is_active = False
                url_mapping.updated_at = datetime.now(timezone.utc)
                session.commit()
                
                logger.info(f"Deleted retailer URL mapping: {url_id}")
                return True
        except Exception as e:
            logger.error(f"DatabaseManager.delete_retailer_url({url_id}) failed: {e}")
            return False

    def get_default_retailer_url(self, retailer: str) -> Optional[Dict[str, Any]]:
        """Get default URL for a retailer"""
        try:
            with self.get_session() as session:
                url_mapping = (
                    session.query(RetailerUrlModel)
                    .filter(
                        RetailerUrlModel.retailer == retailer,
                        RetailerUrlModel.is_default == True,
                        RetailerUrlModel.is_active == True
                    )
                    .first()
                )
                
                if url_mapping:
                    return {
                        "id": url_mapping.id,
                        "retailer": url_mapping.retailer,
                        "website_name": url_mapping.website_name,
                        "starting_url": url_mapping.starting_url,
                        "is_default": url_mapping.is_default,
                        "is_active": url_mapping.is_active,
                    }
                return None
        except Exception as e:
            logger.error(f"DatabaseManager.get_default_retailer_url({retailer}) failed: {e}")
            return None

    def initialize_default_retailer_urls(self):
        """Initialize default retailer URL mappings - starts empty for user configuration"""
        try:
            # Check if we already have retailer URLs
            existing_urls = self.get_retailer_urls()
            if existing_urls:
                logger.info("Retailer URLs already exist, skipping initialization")
                return
            
            # Start with empty configuration - users will add their own retailers
            logger.info("Retailer URL table initialized (empty) - ready for user configuration")
            
        except Exception as e:
            logger.error(f"Failed to initialize retailer URLs table: {e}")

    # Secret Vault Management
    def create_secret(self, site_name: str, site_url: str, username: str = None, password: str = None, additional_fields: Dict[str, Any] = None) -> str:
        """Create a new secret vault entry"""
        try:
            with self.get_session() as session:
                # Encrypt sensitive data (basic implementation - in production use proper encryption)
                encrypted_password = self._encrypt_data(password) if password else None
                encrypted_username = self._encrypt_data(username) if username else None
                
                secret = SecretVaultModel(
                    site_name=site_name,
                    site_url=site_url,
                    username=encrypted_username,
                    password=encrypted_password,
                    additional_fields=additional_fields or {},
                    is_active=True
                )
                session.add(secret)
                session.commit()
                logger.info(f"Created secret vault entry for {site_name}")
                return secret.id
        except Exception as e:
            logger.error(f"DatabaseManager.create_secret() failed: {e}")
            raise

    def get_secrets(self, site_name: str = None, include_passwords: bool = False) -> List[SecretVault]:
        """Get secret vault entries"""
        try:
            # Check if table exists
            from sqlalchemy import inspect
            inspector = inspect(self.engine)
            if 'secret_vault' not in inspector.get_table_names():
                logger.warning("secret_vault table does not exist, returning empty list")
                return []
            
            with self.get_session() as session:
                query = session.query(SecretVaultModel).filter(SecretVaultModel.is_active == True)
                if site_name:
                    query = query.filter(SecretVaultModel.site_name == site_name)
                
                secrets = query.order_by(SecretVaultModel.created_at.desc()).all()
                result = []
                for secret in secrets:
                    # Decrypt sensitive data
                    decrypted_username = self._decrypt_data(secret.username) if secret.username else None
                    decrypted_password = self._decrypt_data(secret.password) if secret.password and include_passwords else None
                    
                    result.append(SecretVault(
                        id=secret.id,
                        site_name=secret.site_name,
                        site_url=secret.site_url,
                        username=decrypted_username,
                        password=decrypted_password,
                        additional_fields=secret.additional_fields,
                        is_active=secret.is_active,
                        created_at=secret.created_at,
                        updated_at=secret.updated_at
                    ))
                return result
        except Exception as e:
            logger.error(f"DatabaseManager.get_secrets() failed: {e}")
            return []

    def get_secret(self, secret_id: str, include_password: bool = False) -> Optional[SecretVault]:
        """Get a specific secret vault entry"""
        try:
            with self.get_session() as session:
                secret = session.query(SecretVaultModel).filter(
                    SecretVaultModel.id == secret_id,
                    SecretVaultModel.is_active == True
                ).first()
                
                if secret:
                    # Decrypt sensitive data
                    decrypted_username = self._decrypt_data(secret.username) if secret.username else None
                    decrypted_password = self._decrypt_data(secret.password) if secret.password and include_password else None
                    
                    return SecretVault(
                        id=secret.id,
                        site_name=secret.site_name,
                        site_url=secret.site_url,
                        username=decrypted_username,
                        password=decrypted_password,
                        additional_fields=secret.additional_fields,
                        is_active=secret.is_active,
                        created_at=secret.created_at,
                        updated_at=secret.updated_at
                    )
                return None
        except Exception as e:
            logger.error(f"DatabaseManager.get_secret({secret_id}) failed: {e}")
            return None

    def update_secret(self, secret_id: str, site_name: str = None, site_url: str = None, username: str = None, password: str = None, additional_fields: Dict[str, Any] = None) -> bool:
        """Update a secret vault entry"""
        try:
            with self.get_session() as session:
                secret = session.query(SecretVaultModel).filter(
                    SecretVaultModel.id == secret_id,
                    SecretVaultModel.is_active == True
                ).first()
                
                if not secret:
                    return False
                
                # Update fields
                if site_name is not None:
                    secret.site_name = site_name
                if site_url is not None:
                    secret.site_url = site_url
                if username is not None:
                    secret.username = self._encrypt_data(username) if username else None
                if password is not None:
                    secret.password = self._encrypt_data(password) if password else None
                if additional_fields is not None:
                    secret.additional_fields = additional_fields
                
                secret.updated_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(f"Updated secret vault entry {secret_id}")
                return True
        except Exception as e:
            logger.error(f"DatabaseManager.update_secret({secret_id}) failed: {e}")
            return False

    def delete_secret(self, secret_id: str) -> bool:
        """Delete (deactivate) a secret vault entry"""
        try:
            with self.get_session() as session:
                secret = session.query(SecretVaultModel).filter(
                    SecretVaultModel.id == secret_id,
                    SecretVaultModel.is_active == True
                ).first()
                
                if not secret:
                    return False
                
                secret.is_active = False
                secret.updated_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(f"Deleted secret vault entry {secret_id}")
                return True
        except Exception as e:
            logger.error(f"DatabaseManager.delete_secret({secret_id}) failed: {e}")
            return False

    def _encrypt_data(self, data: str) -> str:
        """Basic encryption for sensitive data (implement proper encryption in production)"""
        if not data:
            return None
        # This is a basic implementation - use proper encryption in production
        import base64
        return base64.b64encode(data.encode()).decode()

    def _decrypt_data(self, encrypted_data: str) -> str:
        """Basic decryption for sensitive data (implement proper decryption in production)"""
        if not encrypted_data:
            return None
        # This is a basic implementation - use proper decryption in production
        import base64
        try:
            return base64.b64decode(encrypted_data.encode()).decode()
        except Exception:
            return encrypted_data  # Return as-is if decryption fails
