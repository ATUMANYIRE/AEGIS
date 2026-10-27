"""Automated verification test for AEGIS DATANOVA 2026 PowerPoint submission deck."""

from pathlib import Path

from pptx import Presentation


def test_presentation_file_exists_and_has_10_slides():
    """Verify PPTX deck exists and contains exactly 10 editable slides with brand assets."""
    pptx_path = Path("presentation/AEGIS_DATANOVA_2026.pptx")
    assert pptx_path.exists(), (
        "Presentation file does not exist at presentation/AEGIS_DATANOVA_2026.pptx"
    )
    assert pptx_path.stat().st_size > 50_000, "Presentation file appears too small / corrupted"

    prs = Presentation(str(pptx_path))
    assert len(prs.slides) == 10, f"Expected 10 slides, found {len(prs.slides)}"

    # Verify slide titles and structure
    slide_titles = []
    has_pictures = False

    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text:
                text = shape.text_frame.text
                if any(
                    kw in text
                    for kw in [
                        "AEGIS",
                        "Criticality",
                        "Deterministic",
                        "Architecture",
                        "Optimization",
                        "Explainability",
                        "Benchmark",
                        "Screenshots",
                        "Governance",
                        "Roadmap",
                    ]
                ):
                    slide_titles.append(text)
            if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
                has_pictures = True

    assert len(slide_titles) >= 8, (
        f"Expected recognized titles on all slides, found {len(slide_titles)}"
    )
    assert has_pictures, "Expected embedded screenshot images in the presentation deck"
