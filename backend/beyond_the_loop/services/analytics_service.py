import logging
import stripe
import os
from datetime import datetime, timedelta
from fastapi import HTTPException

from beyond_the_loop.models.analytics import EngagementScoreResponse, TopModelsResponse, TopUsersResponse, TopAssistantsResponse, TotalMessagesResponse, PowerUsersResponse
from open_webui.internal.db import get_db
from beyond_the_loop.models.completions import Completion
from beyond_the_loop.models.users import (
    User,
    get_users_by_company,
    get_active_users_by_company,
)
from beyond_the_loop.models.companies import Companies, Company
from sqlalchemy import func, case

log = logging.getLogger(__name__)

# Initialize Stripe API key
stripe.api_key = os.environ.get('STRIPE_API_KEY')


class AnalyticsService:
    def __init__(self):
        pass

    @staticmethod
    def calculate_engagement_score_by_company(company_id: str):
        """
        Returns the adoption rate: percentage of users for the user's company
        that logged in in the last 30 days.
        """

        try:
            # Calculate timestamp for 30 days ago
            thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())

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

            data = {
                "total_users": total_users,
                "active_users": active_users,
                "adoption_rate": round(adoption_rate, 2),
            }

            return EngagementScoreResponse.from_data(data)
        except Exception as e:
            log.error(f"Error calculating adoption rate: {e}")

    @staticmethod
    def get_top_models_by_company(company_id: str, start_date: str, end_date: str):
        if start_date:
            start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_timestamp = int(start_date_dt.timestamp())
        else:
            raise HTTPException(status_code=400, detail="Start date is required.")

        if end_date:
            end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_date_dt = datetime(end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59)
            end_timestamp = int(end_date_dt.timestamp())
        else:
            end_date_dt = datetime.now()
            end_date_dt = datetime(end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59)
            end_timestamp = int(end_date_dt.timestamp())

        if start_timestamp > end_timestamp:
            raise HTTPException(status_code=400, detail="Start date must be before end date.")

        with get_db() as db:
            company_users = db.query(User.id).filter_by(company_id=company_id).all()
            company_user_ids = [u.id for u in company_users]

            top_models = (
                db.query(
                    Completion.model,
                    func.sum(Completion.credits_used).label("credits_used"),
                    func.count(Completion.id).label("message_count"),
                )
                .filter(
                    Completion.assistant == None,
                    Completion.created_at >= start_timestamp,
                    Completion.created_at <= end_timestamp,
                    Completion.user_id.in_(company_user_ids),
                    Completion.from_agent == False,
                )
                .group_by(
                    Completion.model
                )
                .order_by(
                    func.sum(Completion.credits_used).desc()
                )
                .all()
            )

        if not top_models:
            return {"message": "No data found for the given parameters."}

        return TopModelsResponse.from_query_result(top_models)

    @staticmethod
    def get_top_users_by_company(company_id: str, start_date: str, end_date: str):
        if start_date:
            start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_timestamp = int(start_date_dt.timestamp())
        else:
            raise HTTPException(status_code=400, detail="Start date is required.")

        if end_date:
            end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_date_dt = datetime(
                end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59
            )
            end_timestamp = int(end_date_dt.timestamp())
        else:
            end_date_dt = datetime.now()
            end_date_dt = datetime(
                end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59
            )
            end_timestamp = int(end_date_dt.timestamp())

        if start_timestamp > end_timestamp:
            raise HTTPException(status_code=400, detail="Start date must be before end date.")

        with get_db() as db:
            base_query = (
                db.query(Completion)
                .join(User, User.id == Completion.user_id)
                .filter(
                    Completion.from_agent == False,
                    Completion.created_at >= start_timestamp,
                    Completion.created_at <= end_timestamp,
                    User.company_id == company_id,
                )
            )

            model_counts = (
                base_query.with_entities(
                    Completion.user_id,
                    Completion.model,
                    func.count(Completion.id).label("model_count"),
                )
                .group_by(Completion.user_id, Completion.model)
                .subquery()
            )

            model_ranked = (
                db.query(
                    model_counts.c.user_id,
                    model_counts.c.model,
                    func.row_number()
                    .over(
                        partition_by=model_counts.c.user_id,
                        order_by=model_counts.c.model_count.desc(),
                    )
                    .label("rnk"),
                )
                .subquery()
            )

            top_model_subq = (
                db.query(model_ranked.c.user_id, model_ranked.c.model)
                .filter(model_ranked.c.rnk == 1)
                .subquery()
            )

            assistant_counts = (
                base_query.filter(Completion.assistant.isnot(None))
                .with_entities(
                    Completion.user_id,
                    Completion.assistant,
                    func.count(Completion.id).label("assistant_count"),
                )
                .group_by(Completion.user_id, Completion.assistant)
                .subquery()
            )

            assistant_ranked = (
                db.query(
                    assistant_counts.c.user_id,
                    assistant_counts.c.assistant,
                    func.row_number()
                    .over(
                        partition_by=assistant_counts.c.user_id,
                        order_by=assistant_counts.c.assistant_count.desc(),
                    )
                    .label("rnk"),
                )
                .subquery()
            )

            top_assistant_subq = (
                db.query(
                    assistant_ranked.c.user_id,
                    assistant_ranked.c.assistant,
                )
                .filter(assistant_ranked.c.rnk == 1)
                .subquery()
            )

            top_users = (
                base_query.with_entities(
                    Completion.user_id,
                    func.sum(Completion.credits_used).label("total_credits_used"),
                    func.count(Completion.id).label("message_count"),
                    (
                            func.sum(case((Completion.assistant.isnot(None), 1), else_=0))
                            * 100.0
                            / func.count(Completion.id)
                    ).label("assistant_message_percentage"),
                    User.first_name,
                    User.last_name,
                    User.email,
                    User.profile_image_url,
                    top_model_subq.c.model.label("top_model"),
                    top_assistant_subq.c.assistant.label("top_assistant"),
                )
                .outerjoin(top_model_subq, top_model_subq.c.user_id == Completion.user_id)
                .outerjoin(top_assistant_subq, top_assistant_subq.c.user_id == Completion.user_id)
                .group_by(
                    Completion.user_id,
                    User.first_name,
                    User.last_name,
                    User.email,
                    User.profile_image_url,
                    top_model_subq.c.model,
                    top_assistant_subq.c.assistant,
                )
                .order_by(func.sum(Completion.credits_used).desc())
                .all()
            )

            return TopUsersResponse.from_query_result(top_users)

    @staticmethod
    def get_top_assistants_by_company(company_id: str, start_date: str, end_date: str):
        if start_date:
            start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_timestamp = int(start_date_dt.timestamp())
        else:
            raise HTTPException(status_code=400, detail="Start date is required.")

        if end_date:
            end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_date_dt = datetime(end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59)
            end_timestamp = int(end_date_dt.timestamp())
        else:
            end_date_dt = datetime.now()
            end_date_dt = datetime(end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59)
            end_timestamp = int(end_date_dt.timestamp())

        if start_timestamp > end_timestamp:
            raise HTTPException(status_code=400, detail="Start date must be before end date.")

        with get_db() as db:
            company_users = db.query(User.id).filter_by(company_id=company_id).all()
            company_user_ids = [u.id for u in company_users]

            top_assistants = (
                db.query(
                    Completion.assistant,
                    func.sum(Completion.credits_used).label("total_credits_used"),
                    func.count(Completion.id).label("message_count")
                )
                .filter(
                    Completion.assistant != None,
                    Completion.created_at >= start_timestamp,
                    Completion.created_at <= end_timestamp,
                    Completion.user_id.in_(company_user_ids),
                    Completion.from_agent == False,
                )
                .group_by(
                    Completion.assistant
                )
                .order_by(func.sum(Completion.credits_used).desc())
                .all()
            )

            return TopAssistantsResponse.from_query_result(top_assistants)

    @staticmethod
    def get_total_messages_by_company(company_id: str, start_date: str, end_date: str):
        # Parse the date range for monthly aggregation
        start_date_dt, end_date_dt = AnalyticsService._parse_date_range(start_date, end_date)

        with get_db() as db:
            # Get all user IDs for the company
            company_user_ids = db.query(User.id).filter_by(company_id=company_id).all()
            company_user_ids = [u.id for u in company_user_ids]

            monthly_results = (
                db.query(
                    func.to_char(func.to_timestamp(Completion.created_at), 'YYYY-MM').label("month"),
                    func.count(Completion.id).label("total_messages")
                )
                .filter(
                    Completion.user_id.in_(company_user_ids),
                    func.to_timestamp(Completion.created_at) >= start_date_dt,
                    func.to_timestamp(Completion.created_at) <= end_date_dt
                )
                .group_by("month")
                .order_by("month")
                .all()
            )

            monthly_messages = {row.month: row.total_messages for row in monthly_results}

            yearly_results = (
                db.query(
                    func.to_char(func.to_timestamp(Completion.created_at), 'YYYY').label("year"),
                    func.count(Completion.id).label("total_messages")
                )
                .filter(
                    Completion.user_id.in_(company_user_ids)
                )
                .group_by("year")
                .order_by("year")
                .all()
            )
            yearly_messages = {row.year: row.total_messages for row in yearly_results}

        months = AnalyticsService._generate_month_range(start_date_dt, end_date_dt)
        monthly_data = {month: monthly_messages.get(month, 0) for month in months}

        if yearly_messages:
            min_year = min(int(y) for y in yearly_messages.keys())
            max_year = max(int(y) for y in yearly_messages.keys())
        else:
            min_year = start_date_dt.year
            max_year = end_date_dt.year

        years = [str(y) for y in range(min_year, max_year + 1)]
        yearly_data = {year: yearly_messages.get(year, 0) for year in years}

        monthly_percentage_changes = AnalyticsService._calculate_percentage_changes(monthly_data)
        yearly_percentage_changes = AnalyticsService._calculate_percentage_changes(yearly_data)

        return TotalMessagesResponse.from_data(
            monthly_data=monthly_data,
            monthly_percentage_changes=monthly_percentage_changes,
            yearly_data=yearly_data,
            yearly_percentage_changes=yearly_percentage_changes,
        )

    @staticmethod
    def get_power_users_by_company(company_id: str):
        # Calculate timestamp for 30 days ago
        thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())

        with get_db() as db:
            # Find users with more than 400 messages in the last 30 days
            power_users_query = db.query(
                User.id,
                User.first_name,
                User.last_name,
                User.email,
                User.profile_image_url,
                func.count(Completion.id).label("message_count")
            ).join(
                Completion, User.id == Completion.user_id
            ).filter(
                User.company_id == company_id,
                Completion.created_at >= thirty_days_ago,
                Completion.from_agent == False,
            ).group_by(
                User.id, User.first_name, User.last_name, User.email, User.profile_image_url
            ).having(
                func.count(Completion.id) > 400
            ).order_by(
                func.count(Completion.id).desc()
            ).all()

            # Format the results
            power_users = [
                {
                    "user_id": user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "profile_image_url": profile_image_url,
                    "message_count": message_count
                }
                for user_id, first_name, last_name, email, profile_image_url, message_count in power_users_query
            ]

            # Get total number of users in the company for percentage calculation
            total_users = len(get_users_by_company(company_id))

            # Calculate percentage of power users
            power_users_percentage = (len(power_users) / total_users * 100) if total_users > 0 else 0

        data = {
            "power_users": power_users,
            "power_users_count": len(power_users),
            "total_users": total_users,
            "power_users_percentage": round(power_users_percentage, 2)  # Round to 2 decimal places
        }

        return PowerUsersResponse.from_data(data)

    @staticmethod
    def calculate_credit_consumption_by_company(company_id: str, start_date: str, end_date: str):
        try:
            start_date_dt, end_date_dt = AnalyticsService._parse_date_range(start_date, end_date)

            with get_db() as db:
                company_user_ids = db.query(User.id).filter_by(company_id=company_id).all()
                company_user_ids = [u.id for u in company_user_ids]

                query = db.query(
                    # Format the Unix timestamp as "YYYY-MM"
                    func.to_char(func.to_timestamp(Completion.created_at), 'YYYY-MM').label("month"),
                    func.sum(Completion.credits_used).label("total_billing"),
                ).filter(
                    # Filter using actual timestamps
                    func.to_timestamp(Completion.created_at) >= start_date_dt,
                    func.to_timestamp(Completion.created_at) <= end_date_dt,
                    Completion.user_id.in_(company_user_ids)
                )

                # Execute the query and fetch results
                results = query.group_by("month").order_by("month").all()

                # Convert results to a dictionary
                monthly_billing = {row[0]: float(row[1]) for row in results}

            # Generate month range and calculate data
            months = AnalyticsService._generate_month_range(start_date_dt, end_date_dt)
            billing_data = {month: monthly_billing.get(month, 0) for month in months}
            percentage_changes = AnalyticsService._calculate_percentage_changes(billing_data)

            return {
                "monthly_billing": billing_data,
                "percentage_changes": percentage_changes,
            }
        except Exception as e:
            log.error(f"Error calculating user credit usage: {e}")
            return {"monthly_billing": {}, "percentage_changes": {}}

    @staticmethod
    def calculate_credit_consumption_by_user(user_id: str, start_date: str, end_date: str):
        try:
            start_date_dt, end_date_dt = AnalyticsService._parse_date_range(start_date, end_date)

            with get_db() as db:
                query = db.query(
                    # Format the Unix timestamp as "YYYY-MM"
                    func.to_char(
                        func.to_timestamp(Completion.created_at),
                        'YYYY-MM'
                    ).label("month"),
                    func.sum(Completion.credits_used).label("total_billing"),
                ).filter(
                    # Filter using actual timestamps
                    func.to_timestamp(Completion.created_at) >= start_date_dt,
                    func.to_timestamp(Completion.created_at) <= end_date_dt,
                    Completion.user_id == user_id,
                    Completion.from_agent == False,
                )

                # Execute the query and fetch results
                results = query.group_by("month").order_by("month").all()

                # Convert results to a dictionary
                monthly_billing = {row[0]: float(row[1]) for row in results}

            # Generate month range and calculate data
            months = AnalyticsService._generate_month_range(start_date_dt, end_date_dt)
            billing_data = {month: monthly_billing.get(month, 0) for month in months}
            percentage_changes = AnalyticsService._calculate_percentage_changes(billing_data)

            return {
                "monthly_billing": billing_data,
                "percentage_changes": percentage_changes,
            }
        except Exception as e:
            log.error(f"Error calculating user credit usage: {e}")
            return {"monthly_billing": {}, "percentage_changes": {}}

    @staticmethod
    def _get_current_subscription_date_range(company_id: str):
        """
        Helper method to get the current subscription date range for a company.
        
        Args:
            company_id (str): The company ID to get subscription dates for
            
        Returns:
            tuple: (start_date_str, end_date_str) or (None, None) if error
        """
        try:
            # Get the company to retrieve Stripe customer ID
            company = Companies.get_company_by_id(company_id)
            
            if not company or not company.stripe_customer_id:
                log.error(f"Company {company_id} not found or has no Stripe customer ID")
                return None, None
            
            # Handle companies that don't require subscriptions
            if company.subscription_not_required:
                log.info(f"Company {company_id} does not require subscription, using 30-day period")
                # Use last 30 days for companies without subscriptions
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            
            # Get active subscription from Stripe
            active_subscriptions = stripe.Subscription.list(
                customer=company.stripe_customer_id,
                status='active',
                limit=1
            )
            
            # Check for trial subscriptions if no active subscription
            if not active_subscriptions.data:
                trial_subscriptions = stripe.Subscription.list(
                    customer=company.stripe_customer_id,
                    status='trialing',
                    limit=1
                )
                
                if trial_subscriptions.data:
                    subscription = trial_subscriptions.data[0]
                else:
                    # No active or trial subscription, get the last subscription
                    last_subscriptions = stripe.Subscription.list(
                        customer=company.stripe_customer_id,
                        status='all',
                        limit=1
                    )
                    
                    if not last_subscriptions.data:
                        log.error(f"No subscription found for company {company_id}")
                        return None, None
                    
                    subscription = last_subscriptions.data[0]
            else:
                subscription = active_subscriptions.data[0]
            
            # Get the current billing period start date
            current_period_start = subscription.current_period_start
            start_date = datetime.fromtimestamp(current_period_start)
            
            # Use today as the end date
            end_date = datetime.now()
            
            # Format dates as strings
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
            
            log.info(f"Subscription date range for company {company_id}: {start_date_str} to {end_date_str}")
            return start_date_str, end_date_str
            
        except stripe.error.StripeError as e:
            log.error(f"Stripe error getting subscription date range for company {company_id}: {e}")
            return None, None
        except Exception as e:
            log.error(f"Error getting subscription date range for company {company_id}: {e}")
            return None, None

    @staticmethod
    def _parse_date_range(start_date: str, end_date: str):
        """
        Private helper method to parse start_date and end_date strings with consistent defaults.
        
        Args:
            start_date (str): Start date string in YYYY-MM-DD format or None
            end_date (str): End date string in YYYY-MM-DD format or None
            
        Returns:
            tuple: (start_date_dt, end_date_dt) as datetime objects
            
        Raises:
            HTTPException: If start_date is after end_date
        """
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
            end_date_dt = datetime(end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59)
        else:
            end_date_dt = current_date  # Default to current date
            end_date_dt = datetime(end_date_dt.year, end_date_dt.month, end_date_dt.day, 23, 59, 59)

        if start_date_dt > end_date_dt:
            raise HTTPException(status_code=400, detail="Start date must be before end date.")
            
        return start_date_dt, end_date_dt

    @staticmethod
    def _generate_month_range(start_date_dt: datetime, end_date_dt: datetime):
        """
        Private helper method to generate all months within the specified date range.
        
        Args:
            start_date_dt (datetime): Start date as datetime object
            end_date_dt (datetime): End date as datetime object
            
        Returns:
            list: List of month strings in 'YYYY-MM' format
        """
        months = []
        current_month = start_date_dt.replace(day=1)
        end_month = end_date_dt.replace(day=1)

        while current_month <= end_month:
            months.append(current_month.strftime('%Y-%m'))
            # Move to the first day of next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
        
        return months

    @staticmethod
    def _calculate_percentage_changes(data_dict: dict):
        """
        Private helper method to calculate month-over-month percentage changes.
        
        Args:
            data_dict (dict): Dictionary with month keys and numeric values
            
        Returns:
            dict: Dictionary with month keys and percentage change values
        """
        percentage_changes = {}
        previous_value = None
        for month, value in data_dict.items():
            if previous_value is not None:
                change = ((value - previous_value) / previous_value) * 100 if previous_value != 0 else None
                percentage_changes[month] = round(change, 2) if change is not None else "N/A"
            else:
                percentage_changes[month] = "N/A"
            previous_value = value
        
        return percentage_changes

    @staticmethod
    def calculate_credit_consumption_current_subscription_by_company(company: Company):
        """
        Calculate credit consumption for the current subscription billing period.
        Gets the current subscription from Stripe, uses the current billing period start
        as the start date and today as the end date, then calls calculate_credit_consumption_by_company.
        
        Args:
            company_id (str): The company ID to calculate credit consumption for
            
        Returns:
            dict: Credit consumption data for the current billing period
        """
        # Get the subscription date range
        start_date_str, end_date_str = AnalyticsService._get_current_subscription_date_range(company.id)
        
        if not start_date_str or not end_date_str:
            return {"monthly_billing": 0, "percentage_changes": 0}

        log.info(f"Calculating credit consumption for company {company.id} from {start_date_str} to {end_date_str} (current billing period)")
        
        # Call the existing method with the calculated date range
        credit_consumption_data = AnalyticsService.calculate_credit_consumption_by_company(
            company_id=company.id,
            start_date=start_date_str, 
            end_date=end_date_str
        )
        return {"monthly_billing": sum(credit_consumption_data.get("monthly_billing", {}).values()), "percentage_changes": 0}

    @staticmethod
    def calculate_credit_consumption_current_subscription_by_user(user: User):
        """
        Calculate credit consumption for the current subscription billing period for a specific user.
        Gets the user's company subscription from Stripe, uses the current billing period start
        as the start date and today as the end date, then calls calculate_credit_consumption_by_user.

        Args:
            user (User): The user object to calculate credit consumption for

        Returns:
            dict: Credit consumption data for the current billing period
        """
        # Get the user to retrieve their company_id
        start_date_str, end_date_str = AnalyticsService._get_current_subscription_date_range(user.company_id)

        if not start_date_str or not end_date_str:
            return {"monthly_billing": 0, "percentage_changes": 0}

        log.info(f"Calculating credit consumption for user {user.id} from {start_date_str} to {end_date_str} (current billing period)")

        # Call the existing method with the calculated date range
        credit_consumption_data = AnalyticsService.calculate_credit_consumption_by_user(
            user_id=user.id,
            start_date=start_date_str,
            end_date=end_date_str
        )
        return {"monthly_billing": sum(credit_consumption_data.get("monthly_billing", {}).values()), "percentage_changes": 0}
