# VerifyOps recorded demonstration

[Open the working app](https://verifyops.vercel.app/demo) · [Watch the continuous recording](https://verifyops.vercel.app/demo/recording) · [Download the WebM](../frontend/apps/demo/assets/media/walkthrough.webm) · [Capture/source manifest](demos/interactive-recording.json)

![Actual guided browser journey](assets/demos/verifyops-interactive-demo.gif)

The GIF is a six-frame preview. The WebM is a Playwright screen recording of the browser journey and the server results. The cases are the original development incidents.

| Stage | Actual captured behavior |
| --- | --- |
| 1 | choose case |
| 2 | checked proposal |
| 3 | executed evidence |
| 4 | false repair blocked |
| 5 | independent regressions |
| 6 | reviewed result |

## Scope and provenance

Video SHA256: `e389f77016b7fd4f06963afe96f8ad350ed64fc33f6618bed2792f51e46d4c76`. The [manifest](demos/interactive-recording.json) contains frame hashes, source hashes, browser checks and capture scope. Public review/action stages reconstruct isolated fixtures; browser-local signed branches can replay/fork until expiry. The recording is not a globally durable approval/execution claim.

## Reproduce

```sh
python scripts/demos/public_demo_browser.py --record --publish-assets --output artifacts/generated/demo-capture
```

The public browser runner starts an isolated temporary local app by default; --url selects the deployed app. Source hashes bind the actual working tree at capture. Raw captures and generated state stay ignored.

Older private workbench/dbt captures remain available in docs/assets and their dated technical narratives; they show a different, explicitly scoped private workflow.

[Current system layout](development/LAYOUT.md) · [Private/public architecture](architecture/OVERVIEW.md) · [Evaluation limits](evaluation/README.md).

## Product workspace recording

[Watch the file-to-report journey](https://verifyops.vercel.app/uploads/recording.html) · [Source and media manifest](demos/uploads-recording.json). The capture shows the landing, empty workspace, source preview, contract review, independent result, quality and SQL evidence, consented save, and saved history.

Reproduce with `python scripts/demos/product_browser.py --record --output artifacts/generated/product-recording`. The optional `--axe` points to pinned axe-core 4.14.0.
