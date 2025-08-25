"""
Task Scheduler Service

This service handles scheduled tasks including daily chat archival.
Uses APScheduler to run tasks at specified times.
"""

import logging
import atexit
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor

from beyond_the_loop.services.chat_archival_service import chat_archival_service
from beyond_the_loop.services.file_archival_service import file_archival_service

log = logging.getLogger(__name__)

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
    
    def trigger_chat_archival_now(self) -> dict:
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
    
    def trigger_file_cleanup_now(self) -> dict:
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
