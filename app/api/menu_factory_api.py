"""Menu Factory API — AI-powered new menu development workflow."""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import MenuDevSession
from app.schemas.menu_factory import AnswerRequest, SessionCreate, SessionResponse

logger = logging.getLogger("smartexec.menu_factory")

router = APIRouter()


@router.post("/sessions")
def create_session(req: SessionCreate, db: Session = Depends(get_db)):
    """Create a new menu development session."""
    session_id = str(uuid.uuid4())
    session = MenuDevSession(
        id=session_id,
        menu_name=req.menu_name,
        status="created",
    )
    db.add(session)
    db.commit()
    return {"id": session_id, "status": "created", "menu_name": req.menu_name}


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    """List all menu development sessions."""
    sessions = db.query(MenuDevSession).order_by(MenuDevSession.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "menu_name": s.menu_name,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get session details."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse.model_validate(session)


@router.post("/sessions/{session_id}/upload")
async def upload_to_session(
    session_id: str,
    text_input: str = Form(default=""),
    file: UploadFile = File(default=None),
    db: Session = Depends(get_db),
):
    """Upload file or text to a session for analysis."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    extracted_text = text_input

    if file:
        from app.services.file_extractor import extract_text

        content = await file.read()
        filename = file.filename or "uploaded_file"
        extracted_text += "\n\n" + extract_text(content, filename)

    # Store in gemini_analysis temporarily
    analysis = dict(session.gemini_analysis) if session.gemini_analysis else {}
    analysis["raw_input"] = extracted_text
    session.gemini_analysis = analysis
    session.status = "uploaded"
    db.commit()

    return {
        "status": "uploaded",
        "text_length": len(extracted_text),
        "message": "Content uploaded. Call /analyze next.",
    }


@router.post("/sessions/{session_id}/analyze")
def analyze_session(session_id: str, db: Session = Depends(get_db)):
    """Run Gemini analysis on uploaded content."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in ("uploaded", "analyzed"):
        raise HTTPException(status_code=400, detail=f"Invalid status: {session.status}")

    from app.services.menu_factory_service import analyze_with_gemini

    try:
        analysis = analyze_with_gemini(session)
        session.gemini_analysis = analysis
        session.status = "analyzed"
        db.commit()
        return {"status": "analyzed", "analysis": analysis}
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/questions")
def get_questions(session_id: str, db: Session = Depends(get_db)):
    """Generate clarifying questions using AI."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in ("analyzed", "questioning"):
        raise HTTPException(status_code=400, detail=f"Invalid status: {session.status}")

    from app.services.menu_factory_service import generate_questions

    try:
        questions = generate_questions(session)
        session.status = "questioning"
        db.commit()
        return {"status": "questioning", "questions": questions}
    except Exception as e:
        logger.error("Question generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/answer")
def submit_answers(
    session_id: str, req: AnswerRequest, db: Session = Depends(get_db)
):
    """Submit answers to the AI's questions."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    qa_history = list(session.qa_history) if session.qa_history else []
    qa_history.extend(req.answers)
    session.qa_history = qa_history
    db.commit()

    return {"status": session.status, "qa_count": len(qa_history)}


@router.post("/sessions/{session_id}/finalize")
def finalize_session(session_id: str, db: Session = Depends(get_db)):
    """Generate the specification document."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from app.services.menu_factory_service import generate_spec

    try:
        spec = generate_spec(session)
        session.spec_markdown = spec
        session.status = "finalized"
        db.commit()
        return {"status": "finalized", "spec_length": len(spec)}
    except Exception as e:
        logger.error("Spec generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/spec")
def get_spec(session_id: str, db: Session = Depends(get_db)):
    """Get the generated specification."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"spec_markdown": session.spec_markdown or ""}


@router.post("/sessions/{session_id}/generate")
def generate_code(session_id: str, db: Session = Depends(get_db)):
    """Generate plugin code from the spec."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.spec_markdown:
        raise HTTPException(status_code=400, detail="Spec not generated yet")

    from app.services.menu_factory_service import generate_plugin_code

    try:
        code = generate_plugin_code(session)
        session.generated_code = code
        session.status = "generated"
        db.commit()
        return {"status": "generated", "code_length": len(code)}
    except Exception as e:
        logger.error("Code generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/download")
def download_plugin(session_id: str, db: Session = Depends(get_db)):
    """Download generated plugin as a ZIP file."""
    session = db.query(MenuDevSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.generated_code:
        raise HTTPException(status_code=400, detail="Code not generated yet")

    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    # Create ZIP in memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        plugin_filename = f"{session.menu_name}_plugin.py"
        zf.writestr(plugin_filename, session.generated_code)
        if session.spec_markdown:
            zf.writestr(f"{session.menu_name}_spec.md", session.spec_markdown)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={session.menu_name}_plugin.zip"
        },
    )
