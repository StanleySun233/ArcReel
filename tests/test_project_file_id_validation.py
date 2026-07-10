from __future__ import annotations

from lib.data_validator import DataValidator


def _project() -> dict:
    return {
        "title": "Demo",
        "content_mode": "narration",
        "style": "Anime",
        "characters": {
            "Alice": {
                "description": "Hero",
                "character_sheet": "fil_character_sheet",
                "reference_image": "fil_character_ref",
            }
        },
        "scenes": {"Room": {"description": "Room", "scene_sheet": "fil_scene_sheet"}},
        "props": {"Key": {"description": "Key", "prop_sheet": "fil_prop_sheet"}},
    }


def test_project_payload_rejects_legacy_media_paths() -> None:
    project = _project()
    project["characters"]["Alice"]["character_sheet"] = "characters/Alice.png"

    result = DataValidator().validate_project_payload(project)

    assert not result.valid
    assert any("character_sheet" in error and "file_id" in error for error in result.errors)


def test_project_payload_accepts_file_id_media_references() -> None:
    result = DataValidator().validate_project_payload(_project())

    assert result.valid
    assert result.errors == []


def test_episode_generated_assets_reject_legacy_media_paths(tmp_path) -> None:
    project_dir = tmp_path / "projects" / "demo"
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text(
        """
        {
          "title": "Demo",
          "content_mode": "narration",
          "style": "Anime",
          "characters": {"Alice": {"description": "Hero"}},
          "scenes": {},
          "props": {}
        }
        """,
        encoding="utf-8",
    )
    (scripts_dir / "episode_1.json").write_text(
        """
        {
          "episode": 1,
          "title": "Episode",
          "content_mode": "narration",
          "segments": [
            {
              "segment_id": "E1S01",
              "duration_seconds": 4,
              "novel_text": "Text",
              "characters_in_segment": ["Alice"],
              "image_prompt": "Image",
              "video_prompt": "Video",
              "generated_assets": {"storyboard_image": "storyboards/E1S01.png"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    result = DataValidator(projects_root=tmp_path / "projects").validate_episode("demo", "episode_1.json")

    assert not result.valid
    assert any("storyboard_image" in error and "file_id" in error for error in result.errors)
