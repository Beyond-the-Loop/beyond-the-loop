"""
Internal cron endpoints — invoked exclusively by K8s CronJobs.

Each endpoint runs one scheduled job synchronously (blocks until done) and
returns its result as JSON. Authentication is a shared-secret header
`X-Internal-Trigger` matched against the `INTERNAL_TRIGGER_SECRET` env var,
which is provisioned via ExternalSecret into both the app pod and the
CronJob's curl container.

Handlers are plain `def` (not `async def`) so FastAPI dispatches them to the
threadpool — the underlying work is synchronous DB/HTTP and would otherwise
block the event loop for the entire job duration.
"""

import logging
import os
import time
from typing import Callable

from fastapi import APIRouter, Header, HTTPException, status

from beyond_the_loop.services.chat_archival_service import chat_archival_service
from beyond_the_loop.services.file_service import file_service
from beyond_the_loop.services.crm_service import crm_service
from beyond_the_loop.services.analytics_service import AnalyticsService
from beyond_the_loop.services.payments_service import payments_service
from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.users import Users

router = APIRouter()
log = logging.getLogger(__name__)


def _authorize(x_internal_trigger: str | None) -> None:
    expected = os.environ.get("INTERNAL_TRIGGER_SECRET")
    if not expected:
        # Fail-closed: never allow triggering if the secret isn't configured on
        # the server side, otherwise anyone hitting the endpoint could run jobs.
        log.error("internal-cron: INTERNAL_TRIGGER_SECRET not set; refusing request")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    if x_internal_trigger != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def _run_batched(items, per_item: Callable, *, requests_per_second: int = 25) -> int:
    processed = 0
    for i in range(0, len(items), requests_per_second):
        batch_start = time.time()
        for item in items[i:i + requests_per_second]:
            per_item(item)
            processed += 1
        elapsed = time.time() - batch_start
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
    return processed


@router.post("/chat-archival")
def run_chat_archival(x_internal_trigger: str | None = Header(default=None)):
    _authorize(x_internal_trigger)
    log.info("internal-cron: chat archival start")
    result = chat_archival_service.run_daily_archival_process()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "chat archival failed"))
    return result


@router.post("/file-cleanup")
def run_file_cleanup(x_internal_trigger: str | None = Header(default=None)):
    _authorize(x_internal_trigger)
    log.info("internal-cron: file cleanup start")
    result = file_service.run_daily_file_cleanup()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "file cleanup failed"))
    return result


@router.post("/companies-adoption-rate")
def run_companies_adoption_rate(x_internal_trigger: str | None = Header(default=None)):
    _authorize(x_internal_trigger)
    log.info("internal-cron: companies adoption rate start")
    companies = Companies.get_all()

    def per_company(company):
        result = AnalyticsService.calculate_engagement_score_by_company(company.id)
        crm_service.update_company_engagement_score(
            company_name=company.name,
            engagement_score=result.engagement_score,
        )

    processed = _run_batched(companies, per_company)
    return {"success": True, "companies_processed": processed}


@router.post("/company-credit-consumption")
def run_company_credit_consumption(x_internal_trigger: str | None = Header(default=None)):
    _authorize(x_internal_trigger)
    log.info("internal-cron: company credit consumption start")
    companies = Companies.get_all()

    def per_company(company):
        credit_consumption = AnalyticsService.calculate_credit_consumption_current_subscription_by_company(
            company
        ).get("monthly_billing", 0)
        crm_service.update_company_credit_consumption(
            company_name=company.name,
            credit_consumption=credit_consumption,
        )

    processed = _run_batched(companies, per_company)
    return {"success": True, "companies_processed": processed}


@router.post("/user-credit-consumption")
def run_user_credit_consumption(x_internal_trigger: str | None = Header(default=None)):
    _authorize(x_internal_trigger)
    log.info("internal-cron: user credit consumption start")
    users = Users.get_all()

    def per_user(user):
        credit_usage = AnalyticsService.calculate_credit_consumption_current_subscription_by_user(
            user
        ).get("monthly_billing", 0)
        crm_service.update_user_credit_usage(user_email=user.email, credit_usage=credit_usage)

    processed = _run_batched(users, per_user)
    return {"success": True, "users_processed": processed}


@router.post("/credit-recharge-check")
def run_credit_recharge_check(x_internal_trigger: str | None = Header(default=None)):
    _authorize(x_internal_trigger)
    log.info("internal-cron: credit recharge checks start")
    result = payments_service.run_credit_recharge_checks()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "credit recharge checks failed"))
    return result
