import json
from http import HTTPStatus

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.responses import Response

from database.event import Event
from database.repository import GenericRepository
from database.session import db_session
from worker.config import celery_app
from workflows.workflow_registry import WorkflowRegistry

router = APIRouter()


@router.post("/", dependencies=[])
def handle_event(
    data: dict,
    session: Session = Depends(db_session),
) -> Response:
    """Handles incoming event submissions.

    This endpoint receives events, stores them in the database,
    and queues them for asynchronous processing. It implements
    a non-blocking pattern to ensure API responsiveness.

    Args:
        data: The event data, validated against EventSchema
        session: Database session injected by FastAPI dependency

    Returns:
        Response: 202 Accepted response with task ID

    Note:
        The endpoint returns immediately after queueing the task.
        Use the task ID in the response to check processing status.
    """
    # Store event in database
    repository = GenericRepository(
        session=session,
        model=Event,
    )
    raw_event = data.model_dump(mode="json")
    event = Event(data=raw_event, workflow_type=get_workflow_type())
    repository.create(obj=event)

    # Queue processing task
    task_id = celery_app.send_task(
        "process_incoming_event",
        args=[str(event.id)],
    )

    # Return acceptance response
    return Response(
        content=json.dumps({"message": f"process_incoming_event started `{task_id}` "}),
        status_code=HTTPStatus.ACCEPTED,
    )


def get_workflow_type() -> str:
    """
    Implement your logic to determine the workflow type based on the event data.
    """
    return WorkflowRegistry.EXAMPLE_CUSTOMER_CARE_WORKFLOW.name
