import {
  e
} from "./chunk-5NF7IPLD.js";
import {
  __spreadValues
} from "./chunk-QHQP2P2Z.js";

// node_modules/@ionic/core/components/p-D7-vHX0A.js
var o = "ionKeyboardDidShow";
var t = "ionKeyboardDidHide";
var i = {};
var d = {};
var a = false;
var s = () => {
  i = {}, d = {}, a = false;
};
var n = (o2) => {
  if (e.getEngine()) f(o2);
  else {
    if (!o2.visualViewport) return;
    d = l(o2.visualViewport), o2.visualViewport.onresize = () => {
      g(o2), p() || b(o2) ? r(o2) : c(o2) && h(o2);
    };
  }
};
var f = (e2) => {
  e2.addEventListener("keyboardDidShow", ((o2) => r(e2, o2))), e2.addEventListener("keyboardDidHide", (() => h(e2)));
};
var r = (e2, o2) => {
  w(e2, o2), a = true;
};
var h = (e2) => {
  y(e2), a = false;
};
var p = () => !a && i.width === d.width && (i.height - d.height) * d.scale > 150;
var b = (e2) => a && !c(e2);
var c = (e2) => a && d.height === e2.innerHeight;
var w = (e2, t2) => {
  const i2 = new CustomEvent(o, { detail: { keyboardHeight: t2 ? t2.keyboardHeight : e2.innerHeight - d.height } });
  e2.dispatchEvent(i2);
};
var y = (e2) => {
  const o2 = new CustomEvent(t);
  e2.dispatchEvent(o2);
};
var g = (e2) => {
  i = __spreadValues({}, d), d = l(e2.visualViewport);
};
var l = (e2) => ({ width: Math.round(e2.width), height: Math.round(e2.height), offsetTop: e2.offsetTop, offsetLeft: e2.offsetLeft, pageTop: e2.pageTop, pageLeft: e2.pageLeft, scale: e2.scale });

export {
  o,
  t,
  s,
  n,
  r,
  h,
  p,
  b,
  c,
  g,
  l
};
//# sourceMappingURL=chunk-SEXJLOP3.js.map
