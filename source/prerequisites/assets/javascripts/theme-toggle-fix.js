(function () {
  function paletteFromInput(input) {
    return {
      media: input.getAttribute("data-md-color-media") || "",
      scheme: input.getAttribute("data-md-color-scheme") || "",
      primary: input.getAttribute("data-md-color-primary") || "",
      accent: input.getAttribute("data-md-color-accent") || "",
    };
  }

  function applyPalette(input) {
    var color = paletteFromInput(input);
    Object.keys(color).forEach(function (key) {
      document.body.setAttribute("data-md-color-" + key, color[key]);
    });
    localStorage.setItem("__palette", JSON.stringify({ color: color }));
  }

  function activeInput(inputs) {
    var bodyScheme = document.body.getAttribute("data-md-color-scheme");
    return (
      inputs.find(function (input) {
        return input.checked;
      }) ||
      inputs.find(function (input) {
        return input.getAttribute("data-md-color-scheme") === bodyScheme;
      }) ||
      inputs[0]
    );
  }

  function syncVisibleToggle(form, inputs) {
    var current = activeInput(inputs);
    inputs.forEach(function (input) {
      var label = input.nextElementSibling;
      if (!label || !label.matches("label[for]")) {
        return;
      }
      if (input === current) {
        input.checked = true;
        label.removeAttribute("hidden");
        label.style.cursor = "pointer";
      } else {
        label.setAttribute("hidden", "");
      }
    });
    form.setAttribute("data-theme-toggle-ready", "true");
  }

  function bindPaletteToggle() {
    var form = document.querySelector("[data-md-component='palette']");
    if (!form) {
      return;
    }

    var inputs = Array.prototype.slice.call(form.querySelectorAll("input.md-option"));
    if (inputs.length < 2) {
      return;
    }

    syncVisibleToggle(form, inputs);
    if (form.getAttribute("data-theme-toggle-bound") === "true") {
      return;
    }
    form.setAttribute("data-theme-toggle-bound", "true");

    form.addEventListener("click", function (event) {
      var label = event.target.closest("label[for]");
      if (!label || !form.contains(label)) {
        return;
      }

      var targetInput = document.getElementById(label.getAttribute("for"));
      if (!targetInput) {
        return;
      }

      event.preventDefault();
      targetInput.checked = true;
      applyPalette(targetInput);
      syncVisibleToggle(form, inputs);
    });
  }

  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(bindPaletteToggle);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindPaletteToggle);
  } else {
    bindPaletteToggle();
  }
})();
