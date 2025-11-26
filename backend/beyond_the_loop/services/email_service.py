import os
from beyond_the_loop.services.loops_service import loops_service


class EmailService:

    def send_invite_mail(self, to_email: str, invite_token: str, admin_name: str, company_name: str):
        """Send a welcome email to newly registered users."""
        try:
            loops_service.send_transactional_email(to_email, "cmi727wo32ga51g0iw8l68hor", data_variables={
                "admin_name": admin_name,
                "workspace_name": company_name,
                "invitation_link": f"{os.getenv('BACKEND_ADDRESS')}/register?inviteToken={invite_token}"
            })
        except Exception as e:
            print(f"Exception when sending invitation email: {e}")

    def send_reset_password_mail(self, to_email: str, reset_token: str, user_name: str):
        """Send a reset password email to users who requested a password reset."""
        try:
            loops_service.send_transactional_email(to_email, "cmi7b233s3wpmyd0iebq70mdz", data_variables={
                "user_name": user_name,
                "reset_link": f"{os.getenv('BACKEND_ADDRESS')}/create-new-password?resetToken={reset_token}"
            })
        except Exception as e:
            print(f"Exception when sending reset password email: {e}")

    def send_registration_mail(self, to_email: str, registration_code: str):
        """Send a welcome email to newly registered admins."""
        try:
            loops_service.send_transactional_email(to_email, "cmi741slw2oet060idwne1aul", data_variables={
                "verification_code": registration_code,
            })
        except Exception as e:
            print(f"Exception when sending registration email: {e}")

    def send_budget_mail_80(self, to_email: str, admin_name: str, company_name: str, billing_page_link: str):
        """Send a budget alert email to admins when the budget is approaching 80%."""
        try:
            loops_service.send_transactional_email(to_email, "cmi74pg602gxmya0ixr7efee0", data_variables={
                "admin_name": admin_name,
                "workspace_name": company_name,
                "billing_page_link": billing_page_link
            })
        except Exception as e:
            print(f"Exception when sending budget 80: {e}")

    def send_budget_mail_100(self, to_email: str, admin_name: str, company_name: str, billing_page_link):
        """Send a budget alert email to admins when the budget is approaching 100%."""
        try:
            loops_service.send_transactional_email(to_email, "cmi77c00o34luya0igdkq62jx", data_variables={
                "admin_name": admin_name,
                "workspace_name": company_name,
                "billing_page_link": billing_page_link
            })
        except Exception as e:
            print(f"Exception when sending budget 100 email: {e}")