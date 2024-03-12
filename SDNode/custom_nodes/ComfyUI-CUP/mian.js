import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const ext = {
  name: "AIGODLIKE.ComfyUI-CUP",
  async init(app) {},
  async setup(app) {
    api.addEventListener("cup.diff", (event) => {});
    api.addEventListener("cup.queue", (event) => {});
  },
};

app.registerExtension(ext);
