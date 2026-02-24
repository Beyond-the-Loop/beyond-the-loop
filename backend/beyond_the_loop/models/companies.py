from datetime import datetime
import json

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional

from sqlalchemy.orm import relationship
from sqlalchemy import String, Column, Text, Boolean, Float, BigInteger, and_

from open_webui.internal.db import get_db, Base
from enum import Enum

# Constants
NO_COMPANY = "NO_COMPANY"

####################
# Company DB Schema
####################

class Company(Base):
    __tablename__ = "company"

    id = Column(String, primary_key=True, unique=True)
    name = Column(String, nullable=False)
    profile_image_url = Column(Text, nullable=True)
    credit_balance = Column(Float, default=0)
    flex_credit_balance = Column(Float, nullable=True)
    auto_recharge = Column(Boolean, default=False)
    size = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    team_function = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    budget_mail_80_sent = Column(Boolean, nullable=True)
    budget_mail_100_sent = Column(Boolean, nullable=True)
    subscription_not_required = Column(Boolean, nullable=True)
    next_credit_charge_check = Column(BigInteger, nullable=True)

    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    domains = relationship("Domain", back_populates="company", cascade="all, delete-orphan")

class CompanyModel(BaseModel):
    id: str
    name: str
    profile_image_url: Optional[str] = None
    credit_balance: Optional[float] = 0
    flex_credit_balance: Optional[float] = None
    auto_recharge: Optional[bool] = False
    size: Optional[str] = None
    industry: Optional[str] = None
    team_function: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    budget_mail_80_sent: Optional[bool] = False
    budget_mail_100_sent: Optional[bool] = False
    subscription_not_required: Optional[bool] = False
    next_credit_charge_check: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

####################
# Forms
####################

class CompanyModelForm(BaseModel):
    id: str
    model_id: str

    model_config = ConfigDict(protected_namespaces=())

class CompanyForm(BaseModel):
    company: dict

class CreateCompanyForm(BaseModel):
    """Request model for creating a new company"""
    company_name: str
    company_size: str
    company_industry: str
    company_team_function: str
    company_profile_image_url: Optional[str] = "/user.png"

class UpdateCompanyForm(BaseModel):
    """Request model for updating company details"""
    name: Optional[str] = None
    profile_image_url: Optional[str] = None

class CompanyConfigResponse(BaseModel):
    """Response model for company configuration"""
    config: dict

class ChatRetentionDays(Enum):
    DAYS_30 = 30
    DAYS_90 = 90
    DAYS_180 = 180
    DAYS_270 = 270
    DAYS_365 = 365

class UpdateCompanyConfigRequest(BaseModel):
    """Request model for updating company configuration"""
    hide_model_logo_in_chat: Optional[bool] = None
    chat_retention_days: Optional[int] = None
    custom_user_notice: Optional[str] = None
    features_web_search: Optional[bool] = None
    features_image_generation: Optional[bool] = None
    
    @field_validator('chat_retention_days')
    @classmethod
    def validate_chat_retention_days(cls, v):
        if v is None:
            return v
        
        valid_values = [days.value for days in ChatRetentionDays]
        if v not in valid_values:
            raise ValueError(f'chat_retention_days must be one of {valid_values}')
        return v

class CompanyResponse(BaseModel):
    id: str
    name: str
    profile_image_url: Optional[str] = None
    default_model: Optional[str] = None
    allowed_models: Optional[str]
    auto_recharge: bool


class CompanyTable:
    def get_all(self):
        try:
            with get_db() as db:
                companies = db.query(Company).all()
                return [CompanyModel.model_validate(company) for company in companies]
        except Exception as e:
            print(f"Error getting companies: {e}")
            return None

    def get_company_by_id(self, company_id: str):
        try:
            with get_db() as db:
                company = db.query(Company).filter_by(id=company_id).first()
                return CompanyModel.model_validate(company)
        except Exception as e:
            print(f"Error getting company: {e}")
            return None


    def update_company_by_id(self, id: str, updated: dict) -> Optional[CompanyModel]:
        try:
            with get_db() as db:
                db.query(Company).filter_by(id=id).update(updated)
                db.commit()

                company = db.query(Company).filter_by(id=id).first()
                return CompanyModel.model_validate(company)
            
        except Exception as e:
            print(f"Error updating company", e)
            return None

    def get_companies_due_for_credit_recharge_check(self) -> list[CompanyModel]:
        try:
            with get_db() as db:
                now_ts = datetime.now().timestamp()

                due_companies = (
                    db.query(Company)
                    .filter(
                        and_(
                            Company.next_credit_charge_check <= now_ts,
                            Company.stripe_customer_id.isnot(None)
                        )
                    )
                    .all()
                )

                return due_companies

        except Exception as e:
            print("Error fetching companies due for credit recharge check:", e)
            return []

    def update_auto_recharge(self, company_id: str, auto_recharge: bool) -> Optional[CompanyModel]:

        try:
            with get_db() as db:
                company = db.query(Company).filter_by(id=company_id).first()
                if not company:
                    print(f"Company with ID {company_id} not found.")
                    return None

                db.query(Company).filter_by(id=company_id).update({"auto_recharge": auto_recharge})
                db.commit()

                updated_company = db.query(Company).filter_by(id=company_id).first()
                return CompanyModel.model_validate(updated_company)

        except Exception as e:
            print(f"Error updating auto_recharge for company {company_id}: {e}")
            return None


    def get_auto_recharge(self, company_id: str) -> Optional[bool]:
        try:
            with get_db() as db:
                company = db.query(Company).filter_by(id=company_id).first()
                if not company:
                    print(f"Company with ID {company_id} not found.")
                    return None

                return company.auto_recharge

        except Exception as e:
            print(f"Error retrieving auto_recharge for company {company_id}: {e}")
            return None
        
        
    def add_model(self, company_id: str, model_id: str) -> bool:
        try:
            with get_db() as db:
                # Fetch the company by its ID
                company = db.query(Company).filter_by(id=company_id).first()
                print("Company: ", company.allowed_models)
                # If company doesn't exist, return False
                if not company:
                    return None
                
                company.allowed_models = '[]' if company.allowed_models is None else company.allowed_models
                # Load current members from JSON
                current_models = json.loads(company.allowed_models)

                # If model_id is not already in the list, add it
                if model_id not in current_models:
                    current_models.append(model_id)

                    payload = {"allowed_models": json.dumps(current_models)}
                    db.query(Company).filter_by(id=company_id).update(payload)
                    db.commit()

                    return True
                else:
                    # Model already exists in the company
                    return False
        except Exception as e:
            # Handle exceptions if any
            print("ERRRO::: ", e)
            return False

    def remove_model(self, company_id: str, model_id: str) -> bool:
        try:
            with get_db() as db:
                # Fetch the company by its ID
                company = db.query(Company).filter_by(id=company_id).first()
                
                # If company doesn't exist, return False
                if not company:
                    return None
                
                # Load current members from JSON
                current_models = json.loads(company.allowed_models)
                
                # If model_id is in the list, remove it
                if model_id in current_models:
                    current_models.remove(model_id)
                    
                    payload = {"allowed_models": json.dumps(current_models)}
                    db.query(Company).filter_by(id=company_id).update(payload)
                    db.commit()
                    return True
                else:
                    # Member not found in the company
                    return False
        except Exception as e:
            # Handle exceptions if any
            return False

    def add_flex_credit_balance(self, company_id: str, credits_to_add: int) -> bool:
        """Add credits to company's balance"""
        with get_db() as db:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                if company.flex_credit_balance is None:
                    company.flex_credit_balance = credits_to_add
                else:
                    company.flex_credit_balance += credits_to_add
                db.commit()
                return True
            return False

    def subtract_credit_balance(self, company_id: str, credits_to_subtract: int) -> bool:
        """Subtract credits from company's balance"""
        with get_db() as db:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                # Initialize available credits from both balances
                credit_balance = company.credit_balance or 0
                flex_credit_balance = company.flex_credit_balance or 0
                
                # First try to subtract from credit_balance
                if credit_balance >= credits_to_subtract:
                    company.credit_balance -= credits_to_subtract
                    db.commit()
                # If credit_balance is not enough, check if combined balance is sufficient
                elif (credit_balance + flex_credit_balance) >= credits_to_subtract:
                    # Subtract what we can from credit_balance
                    remaining_credits = credits_to_subtract - credit_balance
                    company.credit_balance = 0
                    company.flex_credit_balance -= remaining_credits
                    db.commit()
                else:
                    company.credit_balance = 0
                    company.flex_credit_balance = 0
                    db.commit()

    def get_base_credit_balance(self, company_id: str) -> Optional[int]:
        """Get company's base credit balance"""
        with get_db() as db:
            company = db.query(Company).filter(Company.id == company_id).first()
            return company.credit_balance if company else None

    def get_credit_balance(self, company_id: str) -> Optional[int]:
        """Get company's current credit balance"""
        with get_db() as db:
            company = db.query(Company).filter(Company.id == company_id).first()
            return company.credit_balance + (company.flex_credit_balance or 0) if company else None

    def create_company(self, company_data: dict) -> Optional[CompanyModel]:
        """Create a new company"""
        try:
            with get_db() as db:
                company = Company(**company_data)
                db.add(company)
                db.commit()
                db.refresh(company)
                return CompanyModel.model_validate(company)
        except Exception as e:
            print(f"Error creating company: {e}")
            return None

    def get_company_by_stripe_customer_id(self, stripe_customer_id: str) -> Optional[CompanyModel]:
        try:
            with get_db() as db:
                company = db.query(Company).filter_by(stripe_customer_id=stripe_customer_id).first()
                if company:
                    return CompanyModel.model_validate(company)
                return None
        except Exception as e:
            print(f"Error getting company by stripe_customer_id: {e}")
            return None

    def get_eighty_percent_credit_limit(self, company_id: str) -> float:
        """
        Calculate the credit limit at which the 80% warning should be triggered,
        based on the company's subscription plan.
        
        For free plans or when no subscription exists, returns a default value of 1.
        For paid plans, returns 20% of the monthly credit allocation from the subscription.
        """
        import stripe
        try:
            with get_db() as db:
                company = db.query(Company).filter_by(id=company_id).first()
                if not company or not company.stripe_customer_id:
                    return 1  # Default value for free plan

                from beyond_the_loop.routers.payments import payments_service

                subscription = payments_service.get_subscription(company.id)

                if subscription.get("plan") == "free" or subscription.get("plan") == "premium":
                    return 1
                
                plan_id = subscription.get('plan')
                
                if plan_id not in payments_service.SUBSCRIPTION_PLANS:
                    return 1  # Unknown plan
                
                # Calculate 20% of the monthly credit allocation
                # (which means the warning triggers when 80% is used)
                monthly_credits = payments_service.SUBSCRIPTION_PLANS[plan_id].get("credits_per_month")

                return monthly_credits * 0.2
                
        except Exception as e:
            print(f"Error calculating credit limit for company {company_id}: {e}")
            return 1  # Default fallback value

Companies = CompanyTable()
