"""
Chat Archival Service

This service handles automatic archival and deletion of chats based on company retention policies.
- Archives chats after the configured retention period (chat_retention_days)
- Deletes archived chats after 3 months (90 days)
- Excludes pinned chats and chats in folders from automatic archival and deletion
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_
from open_webui.internal.db import get_db
from beyond_the_loop.models.chats import Chat, Chats
from beyond_the_loop.config import get_config_value
from beyond_the_loop.models.users import User

log = logging.getLogger(__name__)

class ChatArchivalService:
    """Service for handling chat archival and deletion operations"""
    
    DELETION_THRESHOLD_DAYS = 90  # 3 months
    
    def __init__(self):
        self.processed_companies = set()
        self.archived_count = 0
        self.deleted_count = 0
    
    def run_daily_archival_process(self) -> dict:
        """
        Run the complete daily archival process for all companies.
        
        Returns:
            dict: Summary of the archival process results
        """
        log.info("Starting daily chat archival process")
        start_time = datetime.now()
        
        # Reset counters
        self.processed_companies.clear()
        self.archived_count = 0
        self.deleted_count = 0
        
        try:
            # Step 1: Archive old chats based on company retention policies
            self._archive_old_chats()
            
            # Step 2: Delete archived chats older than 3 months
            self._delete_old_archived_chats()
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            summary = {
                "success": True,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "companies_processed": len(self.processed_companies),
                "chats_archived": self.archived_count,
                "chats_deleted": self.deleted_count
            }
            
            log.info(f"Daily archival process completed successfully: {summary}")
            return summary
            
        except Exception as e:
            log.error(f"Error during daily archival process: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "companies_processed": len(self.processed_companies),
                "chats_archived": self.archived_count,
                "chats_deleted": self.deleted_count
            }
    
    def _archive_old_chats(self) -> None:
        """Archive chats that exceed the company's retention period"""
        log.info("Starting chat archival process")
        
        with get_db() as db:
            # Get all companies that have users with chats
            companies_with_chats = db.query(Chat.user_id).distinct().all()
            user_ids = [row[0] for row in companies_with_chats]
            
            if not user_ids:
                log.info("No chats found to process")
                return
            
            # Get users and their companies
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            
            # Group users by company
            company_users = {}
            for user in users:
                if user.company_id:
                    if user.company_id not in company_users:
                        company_users[user.company_id] = []
                    company_users[user.company_id].append(user.id)
            
            # Process each company
            for company_id, company_user_ids in company_users.items():
                try:
                    self._archive_company_chats(company_id, company_user_ids)
                    self.processed_companies.add(company_id)
                except Exception as e:
                    log.error(f"Error processing company {company_id}: {e}", exc_info=True)
    
    def _archive_company_chats(self, company_id: str, user_ids: List[str]) -> None:
        """Archive chats for a specific company based on its retention policy"""
        
        # Get company's chat retention policy
        retention_days = get_config_value("data.chat_retention_days", company_id)

        if retention_days is None:
            raise Exception(f"No chat retention policy found for company {company_id}. Please configure chat_retention_days in company settings.")
        
        log.info(f"Processing company {company_id} with {len(user_ids)} users, retention: {retention_days} days")
        
        # Calculate cutoff timestamp (retention_days ago)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        with get_db() as db:
            # Find chats that should be archived
            # Exclude pinned chats and chats in folders from automatic archival
            chats_to_archive = db.query(Chat).filter(
                and_(
                    Chat.user_id.in_(user_ids),
                    Chat.updated_at < cutoff_timestamp,
                    Chat.archived == False,  # Only non-archived chats
                    Chat.pinned != True,     # Exclude pinned chats
                    Chat.folder_id.is_(None) # Exclude chats in folders
                )
            ).all()
            
            if not chats_to_archive:
                log.info(f"No chats to archive for company {company_id}")
                return
            
            # Archive the chats
            archived_chat_ids = [chat.id for chat in chats_to_archive]
            
            result = db.query(Chat).filter(
                Chat.id.in_(archived_chat_ids)
            ).update(
                {
                    "archived": True,
                    "updated_at": int(time.time())
                },
                synchronize_session=False
            )
            
            db.commit()
            
            self.archived_count += result
            log.info(f"Archived {result} chats for company {company_id}")
    
    def _delete_old_archived_chats(self) -> None:
        """Delete archived chats that are older than 3 months"""
        log.info("Starting deletion of old archived chats")
        
        # Calculate cutoff timestamp (90 days ago)
        cutoff_date = datetime.now() - timedelta(days=self.DELETION_THRESHOLD_DAYS)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        with get_db() as db:
            # Find archived chats older than 3 months
            # Exclude pinned chats and chats in folders from automatic deletion
            chats_to_delete = db.query(Chat).filter(
                and_(
                    Chat.archived == True,
                    Chat.updated_at < cutoff_timestamp,
                    Chat.pinned != True,     # Exclude pinned chats
                    Chat.folder_id.is_(None) # Exclude chats in folders
                )
            ).all()
            
            if not chats_to_delete:
                log.info("No archived chats to delete")
                return
            
            chat_ids_to_delete = [chat.id for chat in chats_to_delete]
            
            # Delete the chats (this will also handle shared chats via the existing method)
            deleted_count = 0
            for chat_id in chat_ids_to_delete:
                try:
                    if Chats.delete_chat_by_id(chat_id):
                        deleted_count += 1
                except Exception as e:
                    log.error(f"Error deleting chat {chat_id}: {e}")
            
            self.deleted_count = deleted_count
            log.info(f"Deleted {deleted_count} old archived chats")
    
    def get_archival_stats(self, company_id: Optional[str] = None) -> dict:
        """
        Get statistics about chat archival for a company or globally.
        
        Args:
            company_id: Optional company ID to filter stats
            
        Returns:
            dict: Statistics about chat archival
        """
        with get_db() as db:
            base_query = db.query(Chat)
            
            if company_id:
                # Get users for this company
                users = db.query(User).filter(User.company_id == company_id).all()
                user_ids = [user.id for user in users]
                if not user_ids:
                    return {
                        "total_chats": 0,
                        "archived_chats": 0,
                        "active_chats": 0,
                        "archival_rate": 0.0
                    }
                base_query = base_query.filter(Chat.user_id.in_(user_ids))
            
            total_chats = base_query.count()
            archived_chats = base_query.filter(Chat.archived == True).count()
            active_chats = total_chats - archived_chats
            archival_rate = (archived_chats / total_chats * 100) if total_chats > 0 else 0.0
            
            return {
                "total_chats": total_chats,
                "archived_chats": archived_chats,
                "active_chats": active_chats,
                "archival_rate": round(archival_rate, 2)
            }
    
    def preview_archival_candidates(self, company_id: str) -> dict:
        """
        Preview which chats would be archived for a company without actually archiving them.
        
        Args:
            company_id: Company ID to preview
            
        Returns:
            dict: Preview information about chats that would be archived
        """
        retention_days = get_config_value("data.chat_retention_days", company_id)
        if retention_days is None:
            retention_days = 30
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        with get_db() as db:
            # Get users for this company
            users = db.query(User).filter(User.company_id == company_id).all()
            user_ids = [user.id for user in users]
            
            if not user_ids:
                return {
                    "company_id": company_id,
                    "retention_days": retention_days,
                    "cutoff_date": cutoff_date.isoformat(),
                    "candidates_count": 0,
                    "candidates": []
                }
            
            # Find chats that would be archived
            # Exclude pinned chats and chats in folders from archival preview
            candidates = db.query(Chat).filter(
                and_(
                    Chat.user_id.in_(user_ids),
                    Chat.updated_at < cutoff_timestamp,
                    Chat.archived == False,
                    Chat.pinned != True,     # Exclude pinned chats
                    Chat.folder_id.is_(None) # Exclude chats in folders
                )
            ).order_by(Chat.updated_at.asc()).limit(10).all()  # Limit for preview
            
            candidate_info = []
            for chat in candidates:
                updated_date = datetime.fromtimestamp(chat.updated_at)
                candidate_info.append({
                    "chat_id": chat.id,
                    "title": chat.title,
                    "user_id": chat.user_id,
                    "updated_at": updated_date.isoformat(),
                    "days_old": (datetime.now() - updated_date).days
                })
            
            total_candidates = db.query(Chat).filter(
                and_(
                    Chat.user_id.in_(user_ids),
                    Chat.updated_at < cutoff_timestamp,
                    Chat.archived == False,
                    Chat.pinned != True,     # Exclude pinned chats
                    Chat.folder_id.is_(None) # Exclude chats in folders
                )
            ).count()
            
            return {
                "company_id": company_id,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "candidates_count": total_candidates,
                "candidates": candidate_info
            }


# Global instance
chat_archival_service = ChatArchivalService()
