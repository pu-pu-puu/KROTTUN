window.STATE =
{
  "version": 2,
  "slug": "diagnostics-proxy-controls",
  "dir": "2026-10-24-diagnostics-proxy-controls--wip",
  "title": "KROTTUN: диагностика, редактирование и резервы",
  "mode": "semi",
  "depth": "normal",
  "tier": "T2",
  "briefFile": "2026-10-24-brief.md",
  "memoryFile": "AGENTS.md",
  "memoryOwner": "autopilot",
  "skillDir": "C:/Users/010726Admin/.agents/skills/autopilot",
  "baseCommit": null,
  "startedAt": "2026-10-24T21:02:17+07:00",
  "updatedAt": "2026-10-24T21:11:30+07:00",
  "finishedAt": null,
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-10-24T21:02:17+07:00",
      "finishedAt": "2026-10-24T21:02:30+07:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-10-24T21:02:30+07:00",
      "finishedAt": "2026-10-24T21:03:58+07:00"
    },
    {
      "id": "briefing",
      "status": "skipped",
      "startedAt": "2026-10-24T21:03:57+07:00",
      "finishedAt": "2026-10-24T21:03:57+07:00",
      "note": "Функции выбраны из согласованного описания; внешних решений не требуется"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-10-24T21:03:58+07:00",
      "finishedAt": "2026-10-24T21:10:44+07:00"
    },
    {
      "id": "plan",
      "status": "active",
      "startedAt": "2026-10-24T21:10:44+07:00"
    },
    {
      "id": "build",
      "status": "pending"
    },
    {
      "id": "review",
      "status": "pending"
    },
    {
      "id": "final",
      "status": "pending"
    }
  ],
  "requirements": {
    "total": 4,
    "done": 0,
    "inTicket": 4,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 0,
    "dropped": 0
  },
  "tickets": [
    {
      "id": "01",
      "title": "Редактирование существующего прокси",
      "requirements": [
        "R02",
        "R04"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "gui/app_webview.py",
        "gui/web/index.html",
        "tests/test_proxy_edit.py"
      ],
      "review": "да — фундамент и credentials/целостность хранилища",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "02",
      "title": "Явная очередь резервов",
      "requirements": [
        "R03",
        "R04"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "gui/app_webview.py",
        "gui/web/index.html",
        "tests/test_fallback_controls.py"
      ],
      "review": "да — защита и целостность настроек",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "03",
      "title": "Диагностика одной кнопкой и доставка",
      "requirements": [
        "R01",
        "R04"
      ],
      "blockedBy": [
        "02"
      ],
      "wave": 3,
      "zone": [
        "core/diagnostics.py",
        "gui/app_webview.py",
        "gui/web/index.html",
        "tests/test_diagnostics.py",
        "prototypes/proxy-controls",
        "README.md"
      ],
      "review": "да — защита сети и lifecycle дочернего процесса",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    }
  ],
  "tests": null,
  "debt": {
    "placeholders": [],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [],
  "coverage": {
    "found": 4,
    "fixed": 4,
    "deferred": 0,
    "items": []
  },
  "concerns": [],
  "blind": null,
  "beats": [
    "2026-10-24T21:02:17+07:00",
    "2026-10-24T21:02:30+07:00",
    "2026-10-24T21:03:55+07:00",
    "2026-10-24T21:03:57+07:00",
    "2026-10-24T21:03:58+07:00",
    "2026-10-24T21:10:43+07:00",
    "2026-10-24T21:10:44+07:00",
    "2026-10-24T21:10:46+07:00",
    "2026-10-24T21:10:48+07:00",
    "2026-10-24T21:10:50+07:00",
    "2026-10-24T21:11:29+07:00",
    "2026-10-24T21:11:30+07:00"
  ]
}
