# Service spotlight

Large centered spectrum rings with full service names. Default: a still Claude page showing 5H and WK together. Use `--page codex` for Codex, or `--rotate` to explicitly alternate the two service pages. The demo below shows optional rotation.

![Service spotlight preview](preview.png)

## Demo

![Service spotlight demo](demo.gif)

These are synthetic examples. The original-resolution image is [preview-32.png](preview-32.png).

## Select

From the repository root, with the updated bridge running:

```bash
./displays/idotmatrix/style.sh service-spotlight
```

## Files

- `render.py`: pure drawing function using shared style helpers.
- `style.json`: ID, description, page names, and preview filenames.
- `preview.png`, `preview-32.png`, `demo.gif`: generated, GitHub-friendly examples.

See the [style guide](../README.md) for configuration, status indicators, preview generation, the renderer contract, and rollback.
