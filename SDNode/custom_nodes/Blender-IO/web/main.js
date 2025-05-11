import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const ext = {
  name: "AIGODLIKE.Blender-IO",
  init(app) {
    return
    const serialize = LGraph.prototype.serialize;
    LGraph.prototype.serialize = function (...args) {
      const workflow = serialize.apply(this, args);
      console.log(workflow);
      // for (const node of workflow.nodes) {
      //   f?.apply(this, arguments);
      //   if (!o.inputs) o.inputs = [];
      //   if (o.inputs.length == 0) o.inputs.push({ linkedOutputs: [] });
      //   o.inputs = [{ linkedOutputs: [] }];
      //   for (const out of o.outputs || []) {
      //     if (!out || !out.links) continue;
      //     o.inputs?.[0]?.linkedOutputs?.push(out.name);
      //   }
      //   console.log(o.inputs?.[0]);
      // }
      return workflow;
    };

    let graphToPrompt = app.graphToPrompt;
    app.graphToPrompt = async function () {
      let p = await graphToPrompt.call(app);
      try {
        let outputs = p.output;
        let workflow = p.workflow;
        for (const node of workflow.nodes) {
          if (node.type != "CombineInput") continue;
          const output = outputs[node.id];
          if (!output) continue;
          if (!output.inputs) output.inputs = {};
          output.inputs["linkedOutputs"] = [];
          for (const out of node.outputs || []) {
            if (!out || !out.links) continue;
            output.inputs.linkedOutputs.push(out.name);
          }
          console.log(output.inputs);
          node.widgets_values.push(output.inputs.linkedOutputs);
        }
      } catch (e) {
        console.log(`Failed to filtering group nodes: ${e}`);
      }

      return p;
    };
  },
  setup(app) {},
  beforeRegisterNodeDef(nodeType, nodeData, app) {
    return
    if (nodeType.comfyClass == "CombineInput") {
      const f = nodeType.prototype.serialize;
      nodeType.prototype.serialize = function () {
        const data = f?.call(this, arguments);
        console.log(data);
        return data;
      };
    }
  },
  nodeCreated(node, app) {
    return
    if (node.comfyClass != "CombineInput") return;
    // console.log(node);
    // const gwp = Object.getOwnPropertyDescriptor;
    // for (const w of node.outputs || []) {
    //   let oValue = w.value;
    //   let property = gwp(w, "value") || gwp(w.constructor.prototype, "value");
    //   Object.defineProperty(w, "value", {
    //     get() {
    //       return property?.get?.call(w) || oValue;
    //     },
    //     set(v) {
    //       property?.set?.call(w, v) || (oValue = v);
    //     },
    //   });
    // }

    // const f = node.onSerialize;
    // function onSerialize(o) {
    //   f?.apply(this, arguments);
    //   if (!o.inputs) o.inputs = [];
    //   if (o.inputs.length == 0) o.inputs.push({ linkedOutputs: [] });
    //   o.inputs = [{ linkedOutputs: [] }];
    //   for (const out of o.outputs || []) {
    //     if (!out || !out.links) continue;
    //     o.inputs?.[0]?.linkedOutputs?.push(out.name);
    //   }
    //   console.log(o.inputs?.[0]);
    //   for (var i = 0; i < this.widgets.length; ++i) {
    //     if (this.widgets[i] == btn) {
    //       delete o.widgets_values[i];
    //       o.widgets_values = [...o.widgets_values];
    //       break;
    //     }
    //   }
    // }
    // node.onSerialize = onSerialize;
  },
};

app.registerExtension(ext);
