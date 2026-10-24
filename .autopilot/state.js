window.STATE =
{
  "version": 2,
  "slug": "diagnostics-proxy-controls",
  "dir": "2026-10-24-diagnostics-proxy-controls",
  "title": "KROTTUN: диагностика, редактирование и резервы",
  "mode": "semi",
  "depth": "normal",
  "tier": "T2",
  "briefFile": "2026-10-24-brief.md",
  "memoryFile": "AGENTS.md",
  "memoryOwner": "autopilot",
  "skillDir": "C:/Users/010726Admin/.agents/skills/autopilot",
  "baseCommit": "48b07e6",
  "startedAt": "2026-10-24T21:02:17+07:00",
  "updatedAt": "2026-10-24T22:07:19+07:00",
  "finishedAt": "2026-10-24T22:07:19+07:00",
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
      "status": "done",
      "startedAt": "2026-10-24T21:10:44+07:00",
      "finishedAt": "2026-10-24T21:11:42+07:00"
    },
    {
      "id": "build",
      "status": "done",
      "startedAt": "2026-10-24T21:11:42+07:00",
      "finishedAt": "2026-10-24T21:52:55+07:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-10-24T21:52:55+07:00",
      "finishedAt": "2026-10-24T21:59:48+07:00"
    },
    {
      "id": "final",
      "status": "done",
      "startedAt": "2026-10-24T21:59:48+07:00",
      "finishedAt": "2026-10-24T22:07:19+07:00"
    }
  ],
  "requirements": {
    "total": 4,
    "done": 4,
    "inTicket": 0,
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
      "status": "done",
      "startedAt": "2026-10-24T21:11:43+07:00",
      "finishedAt": "2026-10-24T21:22:58+07:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 104,
        "failed": 0
      },
      "commit": "72fa1c1"
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
      "status": "done",
      "startedAt": "2026-10-24T21:22:59+07:00",
      "finishedAt": "2026-10-24T21:35:33+07:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 109,
        "failed": 0
      },
      "commit": "78821d8"
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
      "status": "done",
      "startedAt": "2026-10-24T21:35:34+07:00",
      "finishedAt": "2026-10-24T21:52:53+07:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 119,
        "failed": 0
      },
      "commit": "fc1aa1b"
    },
    {
      "id": "F1",
      "title": "Точный статус туннеля в диагностике",
      "requirements": [
        "R01",
        "R04"
      ],
      "blockedBy": [],
      "wave": 4,
      "zone": [
        "core/diagnostics.py",
        "tests/test_diagnostics.py"
      ],
      "review": "да — ремонт ветки",
      "model": "сильная",
      "status": "done",
      "startedAt": "2026-10-24T21:56:29+07:00",
      "retries": 0,
      "repairs": 0,
      "finishedAt": "2026-10-24T21:59:46+07:00",
      "tests": {
        "passed": 120,
        "failed": 0
      },
      "commit": "cba2a4c"
    }
  ],
  "tests": {
    "passed": 120,
    "failed": 0
  },
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
  "concerns": [
    "D01: RUNNING edit резервного сервера не должен менять watchdog candidates; обязательный тест в таске 02",
    "core/diagnostics.py:83-98 — protected tunnel row remains pass when HTTPS fails; итог должен учитывать HTTPS либо явно обозначать только прежний runtime health"
  ],
  "blind": {
    "checked": 4,
    "matched": 3,
    "mismatches": [
      "R04: слепой приёмщик не проверял процесс Autopilot: доступ к его артефактам был запрещён для независимости. Три функции подтверждены; процесс выполнен оркестратором и отражён в state/тасках/коммитах."
    ]
  },
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
    "2026-10-24T21:11:30+07:00",
    "2026-10-24T21:11:40+07:00",
    "2026-10-24T21:11:42+07:00",
    "2026-10-24T21:11:43+07:00",
    "2026-10-24T21:15:50+07:00",
    "2026-10-24T21:18:59+07:00",
    "2026-10-24T21:22:57+07:00",
    "2026-10-24T21:22:58+07:00",
    "2026-10-24T21:22:59+07:00",
    "2026-10-24T21:33:30+07:00",
    "2026-10-24T21:35:33+07:00",
    "2026-10-24T21:35:34+07:00",
    "2026-10-24T21:50:17+07:00",
    "2026-10-24T21:52:52+07:00",
    "2026-10-24T21:52:53+07:00",
    "2026-10-24T21:52:55+07:00",
    "2026-10-24T21:56:27+07:00",
    "2026-10-24T21:56:29+07:00",
    "2026-10-24T21:57:38+07:00",
    "2026-10-24T21:59:07+07:00",
    "2026-10-24T21:59:46+07:00",
    "2026-10-24T21:59:48+07:00",
    "2026-10-24T22:04:08+07:00",
    "2026-10-24T22:04:10+07:00",
    "2026-10-24T22:04:12+07:00",
    "2026-10-24T22:07:19+07:00"
  ],
  "report": [
    "Нативный GUI, реальные сетевые проверки/переключение и frozen-worker runtime в этом прогоне не запускались; VM/IPv6/reboot приёмка защиты остаётся открытой."
  ]
}
