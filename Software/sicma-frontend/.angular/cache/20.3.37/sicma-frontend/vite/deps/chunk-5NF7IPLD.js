import {
  d
} from "./chunk-FBOO75ZN.js";

// node_modules/@ionic/core/components/p-CIGNaXM1.js
var r = () => {
  if (void 0 !== d) return d.Capacitor;
};

// node_modules/@ionic/core/components/p-BMPN55of.js
var n;
var t;
!(function(o) {
  o.Unimplemented = "UNIMPLEMENTED", o.Unavailable = "UNAVAILABLE";
})(n || (n = {})), (function(o) {
  o.Body = "body", o.Ionic = "ionic", o.Native = "native", o.None = "none";
})(t || (t = {}));
var e = { getEngine() {
  const n2 = r();
  if (n2?.isPluginAvailable("Keyboard")) return n2.Plugins.Keyboard;
}, getResizeMode() {
  const o = this.getEngine();
  return o?.getResizeMode ? o.getResizeMode().catch(((o2) => {
    if (o2.code !== n.Unimplemented) throw o2;
  })) : Promise.resolve(void 0);
} };

export {
  r,
  t,
  e
};
//# sourceMappingURL=chunk-5NF7IPLD.js.map
