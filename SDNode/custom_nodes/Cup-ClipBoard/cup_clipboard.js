import { app } from "../../scripts/app.js";
import { $el } from "../../scripts/ui.js";


const ext = {
    name: "AIGODLIKE.CUP-CLIPBOARD",
    async init(app) {
    },
    async setup(app) {
        // 添加按钮
        var btnCopy = $el("button", {
            id: "clipbord-copy-button",
            textContent: "CopyTree",
            style: {
                "font-size": "16px",
            },
            onclick: () => {
                var data = window.app.graph.serialize();
                navigator.clipboard.writeText(JSON.stringify(data));
            },
        });
        var btnPaste = $el("button", {
            id: "clipbord-paste-button",
            textContent: "PasteTree",
            style: {
                "font-size": "16px",
            },
            onclick: () => {
                navigator.clipboard.readText().then(text => {
                    try {
                        var data = JSON.parse(text);
                        window.app.loadGraphData(data);
                    } catch (e) {
                        if (e instanceof SyntaxError) {
                            alert("Clipboard data is not valid.");
                        }
                    }
                });
            },
        });
        app.ui.menuContainer.appendChild(
            $el("div.comfy-menu-btns", [btnCopy, btnPaste])
        );
    }
};

app.registerExtension(ext);
