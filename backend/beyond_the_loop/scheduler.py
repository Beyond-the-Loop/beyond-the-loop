"""
Task Scheduler Service

This service handles scheduled tasks including daily chat archival.
Uses APScheduler to run tasks at specified times.
"""

import logging
import atexit
from typing import Optional
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor

from beyond_the_loop.services.chat_archival_service import chat_archival_service
from beyond_the_loop.services.file_archival_service import file_archival_service
from beyond_the_loop.services.crm_service import crm_service
from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.users import Users
from beyond_the_loop.services.analytics_service import AnalyticsService
from beyond_the_loop.services.payments_service import payments_service

log = logging.getLogger(__name__)


def _run_credit_recharge_checks():
    """Execute the credit recharge checks process"""
    log.info("Starting scheduled credit recharge checks process")

    try:
        result = payments_service.run_credit_recharge_checks()

        if result["success"]:
            log.info(f"Credit recharge checks completed successfully: "
                    f"{result['companies_processed']} companies processed")
        else:
            log.error(f"Credit recharge checks failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        log.error(f"Error during scheduled credit recharge checks: {e}", exc_info=True)


class TaskScheduler:
    """Background task scheduler for automated processes"""
    
    def __init__(self):
        self.scheduler: Optional[BackgroundScheduler] = None
        self.is_running = False
    
    def start(self):
        """Start the background scheduler"""
        if self.is_running:
            log.warning("Scheduler is already running")
            return

        try:
            # Configure scheduler with thread pool
            executors = {
                'default': ThreadPoolExecutor(max_workers=2)
            }
            
            job_defaults = {
                'coalesce': True,  # Combine multiple pending executions into one
                'max_instances': 1,  # Only one instance of each job at a time
                'misfire_grace_time': 300  # 5 minutes grace time for missed jobs
            }
            
            self.scheduler = BackgroundScheduler(
                executors=executors,
                job_defaults=job_defaults,
                timezone='Europe/Berlin'  # Adjust timezone as needed
            )
            
            # Schedule daily chat archival at 23:00
            self.scheduler.add_job(
                func=self._run_chat_archival,
                trigger=CronTrigger(hour=23, minute=0),  # Daily at 23:00
                id='daily_chat_archival',
                name='Daily Chat Archival Process',
                replace_existing=True
            )
            
            # Schedule daily file cleanup at 23:30
            self.scheduler.add_job(
                func=self._run_file_cleanup,
                trigger=CronTrigger(hour=23, minute=30),  # Daily at 23:30
                id='daily_file_cleanup',
                name='Daily File Cleanup Process',
                replace_existing=True
            )

            # Schedule daily companies adoption rate calculation at 01:00
            self.scheduler.add_job(
                func=self._trigger_update_companies_adoption_rate,
                trigger=CronTrigger(hour=1, minute=0),  # Daily at 01:00
                id='daily_companies_adoption_rate_calculation',
                name='Daily Companies Adoption Rate Calculation',
                replace_existing=True
            )

            # Schedule daily company credit consumption calculation at 01:30
            self.scheduler.add_job(
                func=self._trigger_update_company_credit_consumption_current_subscription,
                trigger=CronTrigger(hour=1, minute=30),  # Daily at 01:30
                id='daily_company_credit_consumption_calculation',
                name='Daily Company Credit Consumption Calculation',
                replace_existing=True
            )

            # Schedule daily user credit consumption calculation at 02:00
            self.scheduler.add_job(
                func=self._trigger_update_user_credit_consumption_current_subscription,
                trigger=CronTrigger(hour=2, minute=0),  # Daily at 02:00
                id='daily_user_credit_consumption_calculation',
                name='Daily User Credit Consumption Calculation',
                replace_existing=True
            )

            self.scheduler.add_job(
                func=_run_credit_recharge_checks,
                trigger=CronTrigger(hour=1, minute=0),  # Daily at 01:00
                id='daily_credit_recharge_checks',
                name='Daily Credit Recharge Checks',
                replace_existing=True
            )

            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            log.info("Task scheduler started successfully")
            log.info("Scheduled jobs:")
            for job in self.scheduler.get_jobs():
                log.info(f"  - {job.name} (ID: {job.id}): {job.trigger}")
            
            # Register shutdown handler
            atexit.register(self.shutdown)
            
        except Exception as e:
            log.error(f"Failed to start task scheduler: {e}", exc_info=True)
            raise
    
    def shutdown(self):
        """Shutdown the scheduler gracefully"""
        if self.scheduler and self.is_running:
            log.info("Shutting down task scheduler...")
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            log.info("Task scheduler shut down successfully")
    
    def _run_chat_archival(self):
        """Execute the daily chat archival process"""
        log.info("Starting scheduled chat archival process")
        
        try:
            result = chat_archival_service.run_daily_archival_process()
            
            if result["success"]:
                log.info(f"Chat archival completed successfully: "
                        f"{result['chats_archived']} archived, "
                        f"{result['chats_deleted']} deleted, "
                        f"{result['companies_processed']} companies processed")
            else:
                log.error(f"Chat archival failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            log.error(f"Error during scheduled chat archival: {e}", exc_info=True)

    def _run_file_cleanup(self):
        """Execute the daily file cleanup process"""
        log.info("Starting scheduled file cleanup process")
        
        try:
            result = file_archival_service.run_daily_file_cleanup()
            
            if result["success"]:
                log.info(f"File cleanup completed successfully: "
                        f"{result['files_deleted']} deleted, "
                        f"{result['files_protected']} protected, "
                        f"{result['companies_processed']} companies processed")
            else:
                log.error(f"File cleanup failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            log.error(f"Error during scheduled file cleanup: {e}", exc_info=True)

    def _trigger_update_companies_adoption_rate(self) -> dict:
        """Execute the daily companies adoption rate calculation process"""
        log.info("Starting companies adoption rate calculation process")

        try:
            companies = Companies.get_all()

            requests_per_second = 25
            batch_size = requests_per_second

            for i in range(0, len(companies), batch_size):
                batch_start_time = time.time()
                batch = companies[i:i + batch_size]

                for company in batch:
                    result = AnalyticsService.calculate_engagement_score_by_company(company.id)
                    crm_service.update_company_engagement_score(company_name=company.name, engagement_score=result.engagement_score)

                batch_processing_time = time.time() - batch_start_time
                if batch_processing_time < 1.0:
                    time.sleep(1.0 - batch_processing_time)

        except Exception as e:
            log.error(f"Error during companies adoption rate calculation: {e}", exc_info=True)

    def _trigger_update_company_credit_consumption_current_subscription(self) -> dict:
        """Execute the daily company credit consumption calculation process"""
        log.info("Starting company credit consumption calculation process")

        try:
            companies = Companies.get_all()

            requests_per_second = 25
            batch_size = requests_per_second

            for i in range(0, len(companies), batch_size):
                batch_start_time = time.time()
                batch = companies[i:i + batch_size]

                for company in batch:
                    credit_consumption = AnalyticsService.calculate_credit_consumption_current_subscription_by_company(company).get("monthly_billing", 0)
                    crm_service.update_company_credit_consumption(company_name=company.name, credit_consumption=credit_consumption)

                batch_processing_time = time.time() - batch_start_time
                if batch_processing_time < 1.0:
                    time.sleep(1.0 - batch_processing_time)

        except Exception as e:
            log.error(f"Error during update company credit consumption: {e}", exc_info=True)

    def _trigger_update_user_credit_consumption_current_subscription(self) -> dict:
        """Execute the daily user credit consumption calculation process"""
        log.info("Starting user credit consumption calculation process")

        try:
            users = Users.get_all()

            requests_per_second = 25
            batch_size = requests_per_second

            for i in range(0, len(users), batch_size):
                batch_start_time = time.time()
                batch = users[i:i + batch_size]

                for user in batch:
                    credit_usage = AnalyticsService.calculate_credit_consumption_current_subscription_by_user(user).get("monthly_billing", 0)
                    crm_service.update_user_credit_usage(user_email=user.email, credit_usage=credit_usage)

                batch_processing_time = time.time() - batch_start_time
                if batch_processing_time < 1.0:
                    time.sleep(1.0 - batch_processing_time)

        except Exception as e:
            log.error(f"Error during user credit consumption calculation: {e}", exc_info=True)

    def get_scheduler_status(self) -> dict:
        """Get current scheduler status and job information"""
        if not self.scheduler:
            return {
                "running": False,
                "jobs": []
            }
        
        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run": next_run.isoformat() if next_run else None
            })
        
        return {
            "running": self.is_running,
            "jobs": jobs
        }
    
    @staticmethod
    def trigger_chat_archival_now() -> dict:
        """Manually trigger the chat archival process (for testing/admin purposes)"""
        log.info("Manually triggering chat archival process")
        
        try:
            result = chat_archival_service.run_daily_archival_process()
            log.info(f"Manual chat archival completed: {result}")
            return result
        except Exception as e:
            log.error(f"Error during manual chat archival: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def trigger_file_cleanup_now() -> dict:
        """Manually trigger the file cleanup process (for testing/admin purposes)"""
        log.info("Manually triggering file cleanup process")
        
        try:
            result = file_archival_service.run_daily_file_cleanup()
            log.info(f"Manual file cleanup completed: {result}")
            return result
        except Exception as e:
            log.error(f"Error during manual file cleanup: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

# Global scheduler instance
task_scheduler = TaskScheduler()


def start_scheduler():
    """Initialize and start the global task scheduler"""
    try:
        task_scheduler.start()
    except Exception as e:
        log.error(f"Failed to start global task scheduler: {e}")


def shutdown_scheduler():
    """Shutdown the global task scheduler"""
    task_scheduler.shutdown()
