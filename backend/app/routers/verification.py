from fastapi import APIRouter, Depends

from ..dependencies import require_role


router = APIRouter(tags=["verification"])


@router.get("/admin/test")
def admin_test(_: object = Depends(require_role("admin"))) -> dict[str, str]:
    return {"role": "admin", "status": "authorized"}


@router.get("/recruiter/test")
def recruiter_test(_: object = Depends(require_role("recruiter"))) -> dict[str, str]:
    return {"role": "recruiter", "status": "authorized"}


@router.get("/student/test")
def student_test(_: object = Depends(require_role("student"))) -> dict[str, str]:
    return {"role": "student", "status": "authorized"}