import logging
import time
from typing import Optional
import uuid

from open_webui.internal.db import Base, get_db
from open_webui.models.chats import Chats
from beyond_the_loop.models.groups import Groups
from open_webui.env import SRC_LOG_LEVELS

from functools import partial

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

####################
# Domains DB Schema
####################


class Domain(Base):
    __tablename__ = "domain"

    id = Column(String, unique=True, primary_key=True)

    domain_fqdn = Column(String, unique=True, nullable=False)
    dns_approval_record = Column(String, nullable=False)
    ownership_approved = Column(Boolean, default=False)

    company_id = Column(String, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    company = relationship("Company", back_populates="domains")

class DomainModel(BaseModel):
    id: str
    company_id: str

    domain_fqdn: str
    dns_approval_record: str
    ownership_approved: bool


####################
# Forms
####################


class DomainResponse(BaseModel):
    id: str
    company_id: str

    domain_fqdn: str
    ownership_approved: bool
    dns_approval_record: str


class DomainCreateForm(BaseModel):
    domain_fqdn: str


class DomainTable:
    def insert_domain(self, company_id: str, domain_fqdn: str) -> Optional[DomainModel]:
        try:
            with get_db() as db:
                domain = DomainModel(
                    **{
                        "id": str(uuid.uuid4()),
                        "company_id": company_id,
                        "domain_fqdn": domain_fqdn,
                        "ownership_approved": False,
                        "dns_approval_record": f"beyond-the-loop-{int(time.time())}-{uuid.uuid4()}",
                    }
                )
                db.add(domain)
                db.commit()
                db.refresh(domain)
                return DomainModel.model_validate(domain)
        except Exception as e:
            log.error(f"Error creating domain: {e}")
            return None

    def get_domains_by_company_id(self, company_id: str, skip: Optional[int] = None, limit: Optional[int] = None) -> list[DomainModel]:
        try:
            with get_db() as db:
                query = db.query(Domain).filter_by(company_id=company_id)

                if skip:
                    query = query.offset(skip)
                if limit:
                    query = query.limit(limit)
                
                domains = query.all()
                return [DomainModel.model_validate(domain) for domain in domains]

        except Exception as e:
            log.error(f"Error fetching domains by company ID: {e}")
            return []

    def get_domain_by_id(self, id: str) -> Optional[DomainModel]:
        try:
            with get_db() as db:
                domain = db.query(Domain).filter_by(id=id).first()
                return DomainModel.model_validate(domain) if domain else None
        except Exception as e:
            log.error(f"Error fetching domain by ID: {e}")
            return None

    def get_domain_fqdn_already_exists(self, domain_fqdn: str) -> Optional[bool]:
        try:
            with get_db() as db:
                domain = db.query(Domain).filter_by(domain_fqdn=domain_fqdn).first()
                return domain is not None
        except Exception as e:
            log.error(f"Error checking if domain FQDN exists: {e}")
            return None

    def get_domain_by_domain_fqdn(self, domain_fqdn: str) -> Optional[DomainModel]:
        try:
            with get_db() as db:
                domain = db.query(Domain).filter_by(domain_fqdn=domain_fqdn).first()
                return DomainModel.model_validate(domain) if domain else None
        except Exception as e:
            log.error(f"Error fetching domain by FQDN: {e}")
            return None

    def update_ownership_approved_by_id(self, id: str) -> Optional[DomainModel]:
        try:
            with get_db() as db:
                db.query(Domain).filter_by(id=id).update(
                    {
                        "ownership_approved": True
                    }
                )
                db.commit()
                return self.get_domain_by_id(id)
        except Exception as e:
            log.error(f"Error approving domain ownership: {e}")
            return None

    def delete_domain_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                db.query(Domain).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception as e:
            log.error(f"Error removing domain: {e}")
            return False

Domains = DomainTable()
