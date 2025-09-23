import logging
from datetime import datetime, timedelta

from open_webui.internal.db import get_db
from beyond_the_loop.models.completions import Completion
from backend.beyond_the_loop.models.companies import Company
from beyond_the_loop.models.users import (
    User,
    get_users_by_company,
    get_active_users_by_company,
)
from sqlalchemy import func

log = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self):
        pass

    def calculate_adoption_rate(self, user: User = None, company: Company = None):
        """
        Returns the adoption rate: percentage of users for the user's company
        that logged in in the last 30 days.
        """
        if not user and not company:
            return {"total_users": 0, "active_users": 0, "adoption_rate": 0}

        try:
            # Calculate timestamp for 30 days ago
            thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())

            company_id = company.id if company else user.company_id
            # Get total number of users in the company
            total_users = len(get_users_by_company(company_id=company_id))
            # Get number of active users in the last 30 days
            active_users = len(
                get_active_users_by_company(
                    company_id=company_id, since_timestamp=thirty_days_ago
                )
            )
            # Calculate adoption rate as a percentage
            adoption_rate = (active_users / total_users * 100) if total_users > 0 else 0
            return {
                "total_users": total_users,
                "active_users": active_users,
                "adoption_rate": round(adoption_rate, 2),
            }
        except Exception as e:
            log.error(f"Error calculating adoption rate: {e}")
            return {"total_users": 0, "active_users": 0, "adoption_rate": 0}

    def calculate_company_credit_consumption(
        self, company: Company, start_date: str, end_date: str
    ):
        try:
            users = get_users_by_company(company_id=company.id)
            all_billing_data = {}
            all_percentage_changes = {}
            for user in users:
                user_billing = self.calculate_user_credit_consumption(
                    user=user, start_date=start_date, end_date=end_date
                )
                for month, value in user_billing["monthly_billing"].items():
                    if month in all_billing_data:
                        all_billing_data[month] += value
                    else:
                        all_billing_data[month] = value
                for month, change in user_billing["percentage_changes"].items():
                    if month in all_percentage_changes:
                        if all_percentage_changes[month] != "N/A" and change != "N/A":
                            all_percentage_changes[month] += change
                        else:
                            all_percentage_changes[month] = "N/A"
                    else:
                        all_percentage_changes[month] = change
            return {
                "monthly_billing": all_billing_data,
                "percentage_changes": all_percentage_changes,
            }
        except Exception as e:
            log.error(f"Error calculating user credit usage: {e}")
            return {"monthly_billing": {}, "percentage_changes": {}}

    def calculate_user_credit_consumption(
        self, user: User, start_date: str, end_date: str
    ):
        try:
            current_date = datetime.now()
            one_year_ago = current_date.replace(day=1) - timedelta(days=365)

            # Parse start_date
            if start_date:
                start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                start_date_dt = one_year_ago  # Default to one year ago

            # Parse end_date
            if end_date:
                end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_date_dt = datetime(
                    end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59
                )
            else:
                end_date_dt = current_date  # Default to current date
                end_date_dt = datetime(
                    end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59
                )

            if start_date_dt > end_date_dt:
                log.error("Start date cannot be after end date.")
                return {"monthly_billing": {}, "percentage_changes": {}}

            with get_db() as db:
                query = db.query(
                    func.strftime(
                        "%Y-%m", func.datetime(Completion.created_at, "unixepoch")
                    ).label("month"),
                    func.sum(Completion.credits_used).label("total_billing"),
                ).filter(
                    func.datetime(Completion.created_at, "unixepoch")
                    >= start_date_dt.strftime("%Y-%m-%d 00:00:00"),
                    func.datetime(Completion.created_at, "unixepoch")
                    <= end_date_dt.strftime("%Y-%m-%d %H:%M:%S"),
                )

                query = query.filter(Completion.user_id == user.id)

                # Execute the query and fetch results
                results = query.group_by("month").order_by("month").all()

                # Convert results to a dictionary
                monthly_billing = {row[0]: float(row[1]) for row in results}

            # Generate all months within the specified range
            months = []
            current_month = start_date_dt.replace(day=1)
            end_month = end_date_dt.replace(day=1)

            while current_month <= end_month:
                months.append(current_month.strftime("%Y-%m"))
                # Move to the first day of next month
                if current_month.month == 12:
                    current_month = current_month.replace(
                        year=current_month.year + 1, month=1
                    )
                else:
                    current_month = current_month.replace(month=current_month.month + 1)

            billing_data = {month: monthly_billing.get(month, 0) for month in months}

            # Calculate percentage changes month-over-month
            percentage_changes = {}
            previous_value = None
            for month, value in billing_data.items():
                if previous_value is not None:
                    change = (
                        ((value - previous_value) / previous_value) * 100
                        if previous_value != 0
                        else None
                    )
                    percentage_changes[month] = (
                        round(change, 2) if change is not None else "N/A"
                    )
                else:
                    percentage_changes[month] = "N/A"
                previous_value = value

            return {
                "monthly_billing": billing_data,
                "percentage_changes": percentage_changes,
            }
        except Exception as e:
            log.error(f"Error calculating user credit usage: {e}")
            return {"monthly_billing": {}, "percentage_changes": {}}

    def calculate_company_credit_consumption_current_subscription(
        self, company: Company
    ):
        pass

    def calculate_user_credit_consumption_current_subscription(self, user: User):
        pass


analytics_service = AnalyticsService()
