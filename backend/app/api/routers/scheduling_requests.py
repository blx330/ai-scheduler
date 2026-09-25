from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_scheduling_request_parser, require_organizer
from app.api.routers._planning_serializers import serialize_planning_run
from app.api.schemas.scheduling_requests import (
    SchedulingProposal,
    SchedulingRequestConfirmResponse,
    SchedulingRequestParseBody,
    SchedulingRequestReview,
)
from app.application.services.auth_service import SessionIdentity
from app.application.services.scheduling_request_service import (
    SchedulingRequestRejected,
    SchedulingRequestService,
)
from app.infrastructure.integrations.llm.scheduling_request_parser import (
    SchedulingRequestParseError,
    SchedulingRequestParser,
    SchedulingRequestParserUnavailable,
    SchedulingRequestUpstreamError,
)

router = APIRouter(prefix="/scheduling-requests", tags=["scheduling-requests"])

NOTHING_CHANGED = "Nothing was changed."


@router.post("/parse", response_model=SchedulingRequestReview)
def parse_scheduling_request(
    payload: SchedulingRequestParseBody,
    db: Session = Depends(get_db),
    parser: SchedulingRequestParser = Depends(get_scheduling_request_parser),
    identity: SessionIdentity = Depends(require_organizer),
) -> SchedulingRequestReview:
    """Turn plain English into proposed hard constraints for review. Writes nothing."""
    try:
        return SchedulingRequestService(db, parser).parse(payload.text, requester_id=identity.user_id)
    except SchedulingRequestParserUnavailable as exc:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except SchedulingRequestUpstreamError as exc:
        raise _error(
            status.HTTP_502_BAD_GATEWAY, f"{NOTHING_CHANGED} The language model could not be reached; try again."
        ) from exc
    except SchedulingRequestParseError as exc:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{NOTHING_CHANGED} The request could not be understood reliably; try rephrasing it.",
            [str(exc)],
        ) from exc
    except SchedulingRequestRejected as exc:
        raise _rejected(exc) from exc


@router.post("/confirm", response_model=SchedulingRequestConfirmResponse)
def confirm_scheduling_request(
    proposal: SchedulingProposal,
    db: Session = Depends(get_db),
    parser: SchedulingRequestParser = Depends(get_scheduling_request_parser),
    _: SessionIdentity = Depends(require_organizer),
) -> SchedulingRequestConfirmResponse:
    """Re-validate a reviewed proposal, save it on the event, and run the planner."""
    try:
        event, run = SchedulingRequestService(db, parser).confirm(proposal)
    except SchedulingRequestRejected as exc:
        raise _rejected(exc) from exc
    return SchedulingRequestConfirmResponse(event_id=event.id, planning_run=serialize_planning_run(run))


def _rejected(exc: SchedulingRequestRejected) -> HTTPException:
    return _error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"{NOTHING_CHANGED} The request doesn't match this team's data.",
        exc.errors,
    )


def _error(status_code: int, message: str, errors: list[str] | None = None) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"message": message, "errors": errors or []})
