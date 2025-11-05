"""
File Archival Service

This service handles automatic deletion of files after 3 months.
- Deletes files older than 3 months (90 days)
- Excludes files that are part of Knowledge bases (referenced in data.file_ids)
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Set

from open_webui.internal.db import get_db
from beyond_the_loop.models.files import File, Files
from beyond_the_loop.models.knowledge import Knowledge
from beyond_the_loop.models.users import User

log = logging.getLogger(__name__)

class FileArchivalService:
    """Service for handling file deletion operations"""
    
    DELETION_THRESHOLD_DAYS = 90  # 3 months
    
    def __init__(self):
        self.processed_companies = set()
        self.deleted_count = 0
        self.protected_files_count = 0
    
    def run_daily_file_cleanup(self) -> dict:
        """
        Run the complete daily file cleanup process for all companies.
        
        Returns:
            dict: Summary of the cleanup process results
        """
        log.info("Starting daily file cleanup process")
        start_time = datetime.now()
        
        # Reset counters
        self.processed_companies.clear()
        self.deleted_count = 0
        self.protected_files_count = 0
        
        try:
            # Delete old files (excluding those in knowledge bases)
            self._delete_old_files()
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            summary = {
                "success": True,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "companies_processed": len(self.processed_companies),
                "files_deleted": self.deleted_count,
                "files_protected": self.protected_files_count
            }
            
            log.info(f"Daily file cleanup completed successfully: {summary}")
            return summary
            
        except Exception as e:
            log.error(f"Error during daily file cleanup: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "companies_processed": len(self.processed_companies),
                "files_deleted": self.deleted_count,
                "files_protected": self.protected_files_count
            }
    
    def _get_protected_file_ids(self) -> Set[str]:
        """Get all file IDs that are referenced in knowledge bases and should not be deleted"""
        protected_ids = set()
        
        with get_db() as db:
            # Get all knowledge bases that have file_ids in their data
            knowledges = db.query(Knowledge).filter(Knowledge.data.isnot(None)).all()
            
            for knowledge in knowledges:
                if knowledge.data and isinstance(knowledge.data, dict):
                    file_ids = knowledge.data.get("file_ids", [])
                    if isinstance(file_ids, list):
                        protected_ids.update(file_ids)
        
        log.info(f"Found {len(protected_ids)} files protected by knowledge bases")
        return protected_ids
    
    def _delete_old_files(self) -> None:
        """Delete files that are older than 3 months and not protected by knowledge bases"""
        log.info("Starting deletion of old files")
        
        # Calculate cutoff timestamp (90 days ago)
        cutoff_date = datetime.now() - timedelta(days=self.DELETION_THRESHOLD_DAYS)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        # Get protected file IDs
        protected_file_ids = self._get_protected_file_ids()
        
        with get_db() as db:
            # Find files older than 3 months
            old_files = db.query(File).filter(
                File.created_at < cutoff_timestamp
            ).all()
            
            if not old_files:
                log.info("No old files found to process")
                return
            
            log.info(f"Found {len(old_files)} files older than {self.DELETION_THRESHOLD_DAYS} days")
            
            # Group files by company for tracking
            company_files = {}
            
            for file in old_files:
                # Skip protected files
                if file.id in protected_file_ids:
                    self.protected_files_count += 1
                    continue
                
                # Get user's company
                user = db.query(User).filter(User.id == file.user_id).first()
                if user and user.company_id:
                    company_id = user.company_id
                    if company_id not in company_files:
                        company_files[company_id] = []
                    company_files[company_id].append(file)
                    self.processed_companies.add(company_id)
            
            # Delete files for each company
            for company_id, files_to_delete in company_files.items():
                self._delete_company_files(company_id, files_to_delete)
    
    def _delete_company_files(self, company_id: str, files_to_delete: List[File]) -> None:
        """Delete files for a specific company"""
        log.info(f"Processing {len(files_to_delete)} files for company {company_id}")
        
        deleted_count = 0
        
        for file in files_to_delete:
            try:
                # Delete physical file if it exists
                if file.path and os.path.exists(file.path):
                    try:
                        os.remove(file.path)
                        log.debug(f"Deleted physical file: {file.path}")
                    except OSError as e:
                        log.warning(f"Could not delete physical file {file.path}: {e}")
                
                # Delete database record
                if Files.delete_file_by_id(file.id):
                    deleted_count += 1
                    log.debug(f"Deleted file record: {file.id} ({file.filename})")
                else:
                    log.warning(f"Failed to delete file record: {file.id}")
                    
            except Exception as e:
                log.error(f"Error deleting file {file.id}: {e}")
        
        self.deleted_count += deleted_count
        log.info(f"Deleted {deleted_count} files for company {company_id}")
    
    def get_cleanup_stats(self, company_id: Optional[str] = None) -> dict:
        """
        Get statistics about file cleanup for a company or globally.
        
        Args:
            company_id: Optional company ID to filter stats
            
        Returns:
            dict: Statistics about file cleanup
        """
        cutoff_date = datetime.now() - timedelta(days=self.DELETION_THRESHOLD_DAYS)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        # Get protected file IDs
        protected_file_ids = self._get_protected_file_ids()
        
        with get_db() as db:
            base_query = db.query(File)
            
            if company_id:
                # Get users for this company
                users = db.query(User).filter(User.company_id == company_id).all()
                user_ids = [user.id for user in users]
                if not user_ids:
                    return {
                        "total_files": 0,
                        "old_files": 0,
                        "protected_files": 0,
                        "deletable_files": 0
                    }
                base_query = base_query.filter(File.user_id.in_(user_ids))
            
            total_files = base_query.count()
            old_files_query = base_query.filter(File.created_at < cutoff_timestamp)
            old_files = old_files_query.all()
            
            old_files_count = len(old_files)
            protected_count = len([f for f in old_files if f.id in protected_file_ids])
            deletable_count = old_files_count - protected_count
            
            return {
                "total_files": total_files,
                "old_files": old_files_count,
                "protected_files": protected_count,
                "deletable_files": deletable_count,
                "cutoff_date": cutoff_date.isoformat(),
                "threshold_days": self.DELETION_THRESHOLD_DAYS
            }
    
    def preview_cleanup_candidates(self, company_id: Optional[str] = None) -> dict:
        """
        Preview which files would be deleted without actually deleting them.
        
        Args:
            company_id: Optional company ID to preview
            
        Returns:
            dict: Preview information about files that would be deleted
        """
        cutoff_date = datetime.now() - timedelta(days=self.DELETION_THRESHOLD_DAYS)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        # Get protected file IDs
        protected_file_ids = self._get_protected_file_ids()
        
        with get_db() as db:
            base_query = db.query(File).filter(File.created_at < cutoff_timestamp)
            
            if company_id:
                # Get users for this company
                users = db.query(User).filter(User.company_id == company_id).all()
                user_ids = [user.id for user in users]
                if not user_ids:
                    return {
                        "company_id": company_id,
                        "cutoff_date": cutoff_date.isoformat(),
                        "candidates_count": 0,
                        "protected_count": 0,
                        "candidates": []
                    }
                base_query = base_query.filter(File.user_id.in_(user_ids))
            
            # Get old files
            old_files = base_query.order_by(File.created_at.asc()).all()
            
            candidate_info = []
            protected_count = 0
            
            for file in old_files[:20]:  # Limit for preview
                created_date = datetime.fromtimestamp(file.created_at)
                is_protected = file.id in protected_file_ids
                
                if is_protected:
                    protected_count += 1
                else:
                    candidate_info.append({
                        "file_id": file.id,
                        "filename": file.filename,
                        "user_id": file.user_id,
                        "created_at": created_date.isoformat(),
                        "days_old": (datetime.now() - created_date).days,
                        "path": file.path
                    })
            
            total_deletable = len([f for f in old_files if f.id not in protected_file_ids])
            
            return {
                "company_id": company_id,
                "cutoff_date": cutoff_date.isoformat(),
                "threshold_days": self.DELETION_THRESHOLD_DAYS,
                "total_old_files": len(old_files),
                "protected_count": protected_count,
                "candidates_count": total_deletable,
                "candidates": candidate_info
            }


# Global instance
file_archival_service = FileArchivalService()
