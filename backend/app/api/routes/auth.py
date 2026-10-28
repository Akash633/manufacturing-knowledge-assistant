from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, require_roles

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me")
def get_current_user(
    user: AuthenticatedUser = Depends(require_roles()),
):
    return {"subject": user.subject, "roles": sorted(user.roles)}
