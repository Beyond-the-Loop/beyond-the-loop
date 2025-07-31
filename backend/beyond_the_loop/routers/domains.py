import logging
from typing import Optional
import dns.resolver

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
import validators

from open_webui.constants import ERROR_MESSAGES
from beyond_the_loop.models.domains import (
    DomainCreateForm,
    DomainModel,
    Domains,
)
from open_webui.utils.auth import get_admin_user
from open_webui.env import SRC_LOG_LEVELS
from beyond_the_loop.models.users import Users

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

############################
# Domain Config
############################


@router.get("/", response_model=list[DomainModel])
async def get_domains(
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    user=Depends(get_admin_user),
):
    return Domains.get_domains_by_company_id(
        company_id=user.company_id, skip=skip, limit=limit
    )


@router.post("/create", response_model=Optional[DomainModel])
async def create_domain(form_data: DomainCreateForm, user=Depends(get_admin_user)):
    try:
        if not validators.domain(form_data.domain_fqdn):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid domain format. Please provide a valid domain name.",
            )

        if Domains.get_domain_fqdn_already_exists(form_data.domain_fqdn):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Domain already exists. Please provide a different domain name.",
            )

        domain = Domains.insert_domain(
            company_id=user.company_id, domain_fqdn=form_data.domain_fqdn
        )
        return domain
    
    except HTTPException as http_ex:
        raise http_ex
    
    except Exception as e:
        log.error(f"Error creating domain: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.post("/approve/{domain_id}", response_model=Optional[DomainModel])
async def approve_domain(domain_id: str, user=Depends(get_admin_user)):
    try:
        domain = Domains.get_domain_by_id(id=domain_id)
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )

        if domain.company_id != user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
            )

        try:
            resolver = dns.resolver.Resolver()
            resolver.cache = None
            resolve_response = resolver.resolve(domain.domain_fqdn, "TXT")

            resolve_records = [dns_record.to_text() for dns_record in resolve_response.rrset]

            if not resolve_records:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="DNS record not found. Please ensure the TXT record is set up correctly.",
                )

            if f"\"{domain.dns_approval_record}\"" not in resolve_records:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="DNS record does not match the expected approval record.",
                )

        except dns.resolver.NoAnswer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DNS record not found. Please ensure the TXT record is set up correctly.",
            )

        updated_domain = Domains.update_ownership_approved_by_id(id=domain_id)
        return updated_domain

    except Exception as e:
        log.error(f"Error approving domain: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.delete("/delete/{domain_id}", response_model=bool)
async def delete_domain(domain_id: str, user=Depends(get_admin_user)):
    try:
        domain = Domains.get_domain_by_id(domain_id)

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
            )

        if domain.company_id != user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.UNAUTHORIZED,
            )

        return Domains.delete_domain_by_id(domain_id)

    except Exception as e:
        log.error(f"Error deleting domain: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.INTERNAL_SERVER_ERROR,
        )
