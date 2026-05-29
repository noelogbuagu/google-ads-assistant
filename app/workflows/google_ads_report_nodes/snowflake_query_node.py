import os
from datetime import date, timedelta

from core.nodes.base import Node
from core.task import TaskContext
from services.snowflake_client import run_query

COMPLETENESS_THRESHOLD = int(os.environ.get("REPORT_COMPLETENESS_THRESHOLD", "400"))

COMPLETENESS_SQL = """
SELECT COUNT(*) AS ROW_COUNT
FROM DWH.MARKETING.ACQUISITION_MASTER
WHERE DATE = %(check_date)s
  AND BRAND = %(brand)s
  AND SOURCE = 'Google'
"""

MAIN_SQL = """
SELECT
    DATE,
    CAMPAIGN,
    CHANNEL,
    SUM(COST)                       AS COST,
    SUM(IMPRESSIONS)                AS IMPRESSIONS,
    SUM(CLICKS)                     AS CLICKS,
    AVG(CTR)                        AS CTR,
    AVG(CPC)                        AS CPC,
    SUM(NEW_ORDERS)                 AS NEW_ORDERS,
    SUM(ORDERS)                     AS ORDERS,
    SUM(GROSS_REVENUE)              AS GROSS_REVENUE,
    SUM(NEW_GROSS_REVENUE)          AS NEW_GROSS_REVENUE,
    SUM(GROSS_PROFIT)               AS GROSS_PROFIT,
    SUM(NEW_GROSS_PROFIT)           AS NEW_GROSS_PROFIT,
    SUM(SESSIONS)                   AS SESSIONS,
    SUM(NEW_SESSIONS)               AS NEW_SESSIONS,
    SUM(STARTED_ASSESSMENT)         AS STARTED_ASSESSMENT,
    SUM(NEW_STARTED_ASSESSMENT)     AS NEW_STARTED_ASSESSMENT,
    SUM(SUBMITTED_ASSESSMENT)       AS SUBMITTED_ASSESSMENT,
    SUM(NEW_SUBMITTED_ASSESSMENT)   AS NEW_SUBMITTED_ASSESSMENT,
    SUM(BASKET_PAGE)                AS BASKET_PAGE,
    SUM(NEW_BASKET_PAGE)            AS NEW_BASKET_PAGE,
    SUM(PURCHASED)                  AS PURCHASED,
    SUM(NEW_PURCHASED)              AS NEW_PURCHASED
FROM DWH.MARKETING.ACQUISITION_MASTER
WHERE BRAND = %(brand)s
  AND SOURCE = 'Google'
  AND ATTRIBUTION = 'Last Click Attribution'
  AND IS_CAMPAIGN = 1
  AND DATE BETWEEN %(trailing_start)s AND %(reporting_date)s
GROUP BY DATE, CAMPAIGN, CHANNEL
ORDER BY DATE, COST DESC
"""


class SnowflakeQueryNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        try:
            brand = task_context.event.brand
            override_date = task_context.event.override_date

            if override_date:
                reporting_date = override_date
                data_lag_flag = False
            else:
                today = date.today()
                d1 = today - timedelta(days=1)
                rows = await run_query(COMPLETENESS_SQL, {"check_date": d1, "brand": brand})
                count = int(rows[0]["ROW_COUNT"]) if rows else 0
                if count >= COMPLETENESS_THRESHOLD:
                    reporting_date = d1
                    data_lag_flag = False
                else:
                    reporting_date = today - timedelta(days=2)
                    data_lag_flag = True

            trailing_start = reporting_date - timedelta(days=7)

            all_rows = await run_query(MAIN_SQL, {
                "brand": brand,
                "reporting_date": reporting_date,
                "trailing_start": trailing_start,
            })

            reporting_day_rows = [r for r in all_rows if r["DATE"] == reporting_date]
            trailing_rows = [r for r in all_rows if r["DATE"] != reporting_date]

            task_context.update_node(
                "SnowflakeQueryNode",
                reporting_date=reporting_date,
                data_lag_flag=data_lag_flag,
                reporting_day_rows=reporting_day_rows,
                trailing_rows=trailing_rows,
            )
        except Exception as e:
            task_context.metadata["error"] = f"SnowflakeQueryNode failed: {e}"

        return task_context
