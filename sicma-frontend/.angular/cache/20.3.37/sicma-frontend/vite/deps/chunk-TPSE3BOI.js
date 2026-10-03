import {
  d as d2
} from "./chunk-FBOO75ZN.js";
import {
  d,
  n
} from "./chunk-45K2QPHS.js";
import {
  __async
} from "./chunk-QHQP2P2Z.js";

// node_modules/@ionic/core/components/p-BWoa-cki.js
var o = () => n.get("experimentalCloseWatcher", false) && void 0 !== d2 && "CloseWatcher" in d2;
var r = () => {
  document.addEventListener("backbutton", (() => {
  }));
};
var i = () => {
  const e = document;
  let r2 = false;
  const i2 = () => {
    if (r2) return;
    let t = 0, o2 = [];
    const i3 = new CustomEvent("ionBackButton", { bubbles: false, detail: { register(e2, n2) {
      o2.push({ priority: e2, handler: n2, id: t++ });
    } } });
    e.dispatchEvent(i3);
    const a2 = () => {
      if (o2.length > 0) {
        let t2 = { priority: Number.MIN_SAFE_INTEGER, handler: () => {
        }, id: -1 };
        o2.forEach(((e2) => {
          e2.priority >= t2.priority && (t2 = e2);
        })), r2 = true, o2 = o2.filter(((e2) => e2.id !== t2.id)), ((t3) => __async(null, null, function* () {
          try {
            if (t3?.handler) {
              const e2 = t3.handler(a2);
              null != e2 && (yield e2);
            }
          } catch (t4) {
            d("[ion-app] - Exception in startHardwareBackButton:", t4);
          }
        }))(t2).then((() => r2 = false));
      }
    };
    a2();
  };
  if (o()) {
    let e2;
    const n2 = () => {
      e2?.destroy(), e2 = new d2.CloseWatcher(), e2.onclose = () => {
        i2(), n2();
      };
    };
    n2();
  } else e.addEventListener("backbutton", i2);
};
var a = 100;
var s = 99;

export {
  o,
  r,
  i,
  a,
  s
};
//# sourceMappingURL=chunk-TPSE3BOI.js.map
