"""Dagster schedules for GNSS processing."""

from dagster import ScheduleDefinition, RunRequest, ScheduleEvaluationContext
import datetime

from .jobs import daily_gnss_processing_job


def generate_daily_config(context: ScheduleEvaluationContext):
    """Generate configuration for daily GNSS processing."""
    # Get yesterday's date (since GNSS products are typically available the next day)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")

    return RunRequest(
        run_config={
            "ops": {
                "satellite_orbit_sp3": {
                    "config": {
                        "date": date_str,
                        "pride_dir": "./pride_data",
                        "override": False,
                        "source": "all",
                    }
                },
                "satellite_clock_clk": {
                    "config": {
                        "date": date_str,
                        "pride_dir": "./pride_data",
                        "override": False,
                        "source": "all",
                    }
                },
                "code_phase_bias": {
                    "config": {
                        "date": date_str,
                        "pride_dir": "./pride_data",
                        "override": False,
                        "source": "all",
                    }
                },
                "quaternions_obx": {
                    "config": {
                        "date": date_str,
                        "pride_dir": "./pride_data",
                        "override": False,
                        "source": "all",
                    }
                },
                "earth_rotation_parameters_erp": {
                    "config": {
                        "date": date_str,
                        "pride_dir": "./pride_data",
                        "override": False,
                        "source": "all",
                    }
                },
                "pride_config_file": {
                    "config": {
                        "date": date_str,
                        "pride_dir": "./pride_data",
                        "override": False,
                        "source": "all",
                    }
                },
            }
        },
        tags={"date": date_str},
    )


# Daily schedule to run at 2 AM UTC
daily_gnss_schedule = ScheduleDefinition(
    job=daily_gnss_processing_job,
    cron_schedule="0 2 * * *",  # Run at 2 AM UTC every day
    execution_fn=generate_daily_config,
    description="Daily schedule to download GNSS products for the previous day",
)
