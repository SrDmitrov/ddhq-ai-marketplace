# chat-replay

Development rules for this plugin. Usage and the `.chat` format are in `README.md` and `skills/fancy-replay/FORMAT.md`.

- Rebuild the examples after any change to `skills/fancy-replay/src/` or `build.mjs`: `node skills/fancy-replay/build.mjs examples/*.chat`. No dependencies.
- Never hand-edit a built `.html`. Edit `src/` or the `.chat` file and rebuild.
- The two dark-theme blocks in `skills/fancy-replay/src/player.css` must stay identical.
- `examples/` holds only the three committed examples (`hello-world`, `beatles-trip`, `coffe-break-with-questions`). Do not add, rename or remove files there unless the user asks. Built `.html` files there are git-ignored.
- Never put a raw export or a real conversation in this repo.
