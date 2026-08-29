(function () {
  var currentScript = document.currentScript;
  var mathjaxRoot = "/assets/vendor/mathjax";
  if (currentScript && currentScript.src) {
    mathjaxRoot = new URL("../vendor/mathjax", currentScript.src).href;
  }

  window.MathJax = {
    loader: {
      paths: {
        mathjax: mathjaxRoot,
      },
    },
    options: {
      enableAssistiveMml: false,
    },
  };
})();
