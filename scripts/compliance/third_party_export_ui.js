/* Interactive SWIPAT preview for scripts/compliance/SKILL.html. */
(function () {
  "use strict";

  var HEADER = [
    "Package / Component Name",
    "Version",
    "License",
    "Link to Component's License",
    "Method of Distribution",
    "Usage Method with NV proprietary code",
    "Comments",
    "Location where component was downloaded from",
    "Link to internal IT Controlled Repository"
  ];
  var OTHER = "Other (Please describe in Comments)";
  var INTERNAL = "Internal Use Only";
  var SCOPE_HEADER = [
    "Repository Item", "Scope Category", "Artifact Relationship",
    "Distributed by NVIDIA in This Repository", "Executed in Learner Browser",
    "External Source or Package", "Recorded License or Terms",
    "Corroborating Repository Evidence", "Legal Scope Note"
  ];

  function parseLinks(text) {
    var out = [], pattern = /\[([^\]]+)]\(([^)]+)\)/g, match;
    while ((match = pattern.exec(text || ""))) out.push({ label: match[1], url: match[2] });
    return out;
  }

  function section(markdown, heading) {
    var marker = "## " + heading;
    var start = markdown.indexOf(marker);
    if (start < 0) return "";
    var body = markdown.slice(start + marker.length);
    var end = body.indexOf("\n## ");
    return end < 0 ? body : body.slice(0, end);
  }

  function tableRows(markdown, heading) {
    return section(markdown, heading).split(/\r?\n/).filter(function (line) {
      return line.charAt(0) === "|" && !/^\|[|\s:-]+\|?$/.test(line);
    }).map(function (line) {
      return line.replace(/^\||\|$/g, "").split("|").map(function (value) { return value.trim(); });
    }).filter(function (row) {
      return row[0] !== "Scope" && row[0] !== "Repository file" && row[0] !== "Identifier";
    });
  }

  function repoFile(config, path) {
    var blob = /github\.com/i.test(config.repository) ? "/blob/" : "/-/blob/";
    return config.repository.replace(/\/$/, "") + blob +
      encodeURIComponent(config.project_ref).replace(/%2F/g, "/") + "/" +
      path.split("/").map(encodeURIComponent).join("/");
  }

  function npmPage(name, version) {
    return "https://www.npmjs.com/package/" + name.split("/").map(encodeURIComponent).join("/") +
      "/v/" + encodeURIComponent(version);
  }

  function assetIndex(manifest) {
    var out = {};
    (manifest.assets || []).forEach(function (asset) {
      (asset.packages || []).forEach(function (name) {
        if (!out[name]) out[name] = [];
        out[name].push(asset.file);
      });
    });
    return out;
  }

  function vendoredRows(manifest, config) {
    var assets = assetIndex(manifest);
    return (manifest.packages || []).map(function (pkg) {
      var licensePath = "web/nemoclaw/vendor/" + pkg.license_file;
      var relationship = pkg.direct ? "direct" : "transitive";
      return {
        category: "vendored",
        relationship: relationship,
        cells: [
          pkg.name,
          String(pkg.version),
          pkg.license,
          repoFile(config, licensePath),
          OTHER,
          OTHER,
          "Vendored and distributed with the static course as same-origin browser code. " +
            "Relationship: " + relationship + ". Purpose: " + pkg.purpose + " Shipped asset(s): " +
            ((assets[pkg.name] || []).sort().join(", ") || "shared browser bundle") + ". " +
            "Used with NVIDIA-authored Apache-2.0 course source; no proprietary-code claim.",
          npmPage(pkg.name, String(pkg.version)),
          repoFile(config, licensePath)
        ]
      };
    });
  }

  function buildRows(markdown, config) {
    return tableRows(markdown, "Browser runtime and browser-build packages").filter(function (row) {
      return row.length >= 5 && (row[0] === "browser-bundle-input" || row[0] === "browser-build-only");
    }).map(function (row) {
      var scope = row[0], name = row[1], version = row[2];
      return {
        category: "build-input",
        relationship: scope,
        cells: [
          name, version, row[3], npmPage(name, version), INTERNAL, OTHER,
          "Category: " + scope + ". Downloaded by npm during the deterministic browser build and not " +
            "copied as a standalone package into the released static course. " +
            (scope === "browser-bundle-input" ? "Its code contributes to a generated browser bundle." : "It executes only as build tooling.") +
            " No proprietary-code claim.",
          npmPage(name, version), repoFile(config, "scripts/browser-vendor/package-lock.json")
        ]
      };
    });
  }

  function validationRows(markdown, config) {
    return tableRows(markdown, "Python runtime and repository-tool packages").filter(function (row) {
      return row.length >= 5;
    }).map(function (row) {
      var links = parseLinks(row[4]);
      var upstream = (links.find(function (link) { return link.label === "PyPI"; }) || {}).url || "";
      var lock = (links.find(function (link) { return !/^https?:/.test(link.url); }) || {}).url || "THIRD_PARTY_LICENSES.md";
      return {
        category: "validation",
        relationship: row[0],
        cells: [
          row[1], row[2], row[3], upstream, INTERNAL, OTHER,
          "Downloaded into the " + row[0] + " environment for local authoring or repository validation. " +
            "Not vendored in the repository and not shipped in the static learner course. No proprietary-code claim.",
          upstream, repoFile(config, lock)
        ]
      };
    });
  }

  function localRows(markdown, config) {
    return tableRows(markdown, "Direct container, runtime, and operating-system declarations").filter(function (row) {
      return row.length >= 5;
    }).map(function (row) {
      var links = parseLinks(row[4]);
      var upstream = (links.find(function (link) { return /^https?:/.test(link.url); }) || {}).url || "";
      var pathMatch = row[4].match(/`([^`]+(?:Dockerfile|requirements\.txt))`/);
      var cleanEvidence = row[4].replace(/\[([^\]]+)]\(([^)]+)\)/g, "$1");
      return {
        category: "local-authoring",
        relationship: row[0],
        cells: [
          row[1], row[2], row[3], upstream, INTERNAL, OTHER,
          "Category: " + row[0] + ". Referenced or pulled for local authoring and compatibility testing; " +
            "not distributed with the static learner course. " + cleanEvidence,
          upstream || row[1], repoFile(config, pathMatch ? pathMatch[1] : "THIRD_PARTY_LICENSES.md")
        ]
      };
    });
  }

  function csvCell(value) {
    var text = String(value == null ? "" : value);
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  function csv(rows, baseContainer) {
    var all = [
      ["Base Container used (if applicable):", "", baseContainer, "", "", "", "", "", ""],
      ["", "", "", "", "", "", "", "", ""],
      HEADER
    ].concat(rows.map(function (row) { return row.cells; }));
    return all.map(function (row) { return row.map(csvCell).join(","); }).join("\n") + "\n";
  }

  function plainCsv(header, rows) {
    return [header].concat(rows.map(function (row) { return row.cells; }))
      .map(function (row) { return row.map(csvCell).join(","); }).join("\n") + "\n";
  }

  function materialScopeRows(markdown, config) {
    return tableRows(markdown, "Third-party course-material relationships").filter(function (row) {
      return row.length >= 5;
    }).map(function (row) {
      var relationship = row[1];
      var links = parseLinks(row[4]);
      var source = links.length ? links[0].url : row[4];
      var category, distributed, note;
      if (relationship === "recreation") {
        category = "recreated-asset"; distributed = "Yes";
        note = "A repository-authored recreation is distributed; review the recorded source terms before release.";
      } else if (relationship === "conversion") {
        category = "vendored-material"; distributed = "Yes";
        note = "A copied or format-shifted material artifact is distributed; the source terms remain controlling.";
      } else {
        category = "referenced-source"; distributed = "Yes - repository-authored item";
        note = "The repository item is distributed, but the external work is cited, summarized, used as inspiration, or compiled as links rather than vendored wholesale.";
      }
      return { category:category, relationship:relationship, terms:row[3], cells:[
        row[0], category, relationship, distributed, "No", source, row[3], repoFile(config, row[0]),
        "Source label: " + row[2] + ". " + note
      ]};
    });
  }

  function legalSoftwareRows(manifest, markdown, config) {
    var rows = vendoredRows(manifest, config).map(function (row) {
      return {category:"vendored-browser-code", relationship:row.relationship, terms:row.cells[2], cells:[
        row.cells[0] + "@" + row.cells[1], "vendored-browser-code", row.relationship,
        "Yes", "Yes", row.cells[7], row.cells[2], row.cells[8],
        "Copied into the same-origin static course; the repository license text and package source corroborate scope."
      ]};
    });
    buildRows(markdown, config).filter(function (row) {
      return row.relationship === "browser-build-only";
    }).concat(validationRows(markdown, config), localRows(markdown, config)).forEach(function (row) {
      rows.push({category:"tooling-not-distributed", relationship:row.relationship, terms:row.cells[2], cells:[
        row.cells[0] + "@" + row.cells[1], "tooling-not-distributed", row.relationship,
        "No", "No", row.cells[7], row.cells[2], row.cells[8], row.cells[6]
      ]});
    });
    return rows;
  }

  function text(node, value) {
    node.textContent = String(value == null ? "" : value);
  }

  function mount(config, target) {
    return Promise.all([
      fetch(config.vendor_manifest).then(function (response) {
        if (!response.ok) throw new Error("vendor manifest HTTP " + response.status);
        return response.json();
      }),
      fetch(config.inventory).then(function (response) {
        if (!response.ok) throw new Error("inventory HTTP " + response.status);
        return response.text();
      })
    ]).then(function (sources) {
      var rows = vendoredRows(sources[0], config)
        .concat(buildRows(sources[1], config))
        .concat(validationRows(sources[1], config))
        .concat(localRows(sources[1], config));
      var category = target.querySelector("[data-export-category]");
      var relationship = target.querySelector("[data-export-relationship]");
      var license = target.querySelector("[data-export-license]");
      var search = target.querySelector("[data-export-search]");
      var base = target.querySelector("[data-export-base]");
      var body = target.querySelector("tbody");
      var count = target.querySelector("[data-export-count]");

      Array.from(new Set(rows.map(function (row) { return row.cells[2]; }))).sort().forEach(function (value) {
        var option = document.createElement("option"); text(option, value); option.value = value; license.appendChild(option);
      });

      function visibleRows() {
        var query = search.value.trim().toLowerCase();
        return rows.filter(function (row) {
          return (category.value === "all" || row.category === category.value) &&
            (!relationship.value || row.relationship === relationship.value) &&
            (!license.value || row.cells[2] === license.value) &&
            (!query || row.cells.join(" ").toLowerCase().indexOf(query) >= 0);
        });
      }

      function relationshipOptions() {
        var current = relationship.value;
        var options = Array.from(new Set(rows.filter(function (row) {
          return category.value === "all" || row.category === category.value;
        }).map(function (row) { return row.relationship; }))).sort();
        relationship.replaceChildren();
        var any = document.createElement("option"); any.value = ""; text(any, "All relationships"); relationship.appendChild(any);
        options.forEach(function (value) {
          var option = document.createElement("option"); option.value = value; text(option, value); relationship.appendChild(option);
        });
        relationship.value = options.indexOf(current) >= 0 ? current : "";
      }

      function paint() {
        var visible = visibleRows();
        body.replaceChildren();
        visible.forEach(function (row) {
          var tr = document.createElement("tr");
          row.cells.forEach(function (value, index) {
            var td = document.createElement("td");
            if ((index === 3 || index === 7 || index === 8) && /^https?:/.test(value)) {
              var anchor = document.createElement("a"); anchor.href = value; anchor.target = "_blank"; anchor.rel = "noopener noreferrer"; text(anchor, value); td.appendChild(anchor);
            } else text(td, value);
            tr.appendChild(td);
          });
          body.appendChild(tr);
        });
        text(count, visible.length + " component" + (visible.length === 1 ? "" : "s"));
        target.dataset.exportReady = "1";
      }

      category.addEventListener("change", function () { relationshipOptions(); paint(); });
      relationship.addEventListener("change", paint);
      license.addEventListener("change", paint);
      search.addEventListener("input", paint);
      target.querySelector("[data-export-download]").addEventListener("click", function () {
        var blob = new Blob([csv(visibleRows(), base.value)], { type: "text/csv;charset=utf-8" });
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "nemoclaw-third-party-components-" + category.value + ".csv";
        document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(link.href);
      });
      relationshipOptions(); paint();
      return rows;
    }).catch(function (error) {
      target.dataset.exportError = error.message;
      var status = target.querySelector("[data-export-count]");
      text(status, "Preview failed: " + error.message);
      throw error;
    });
  }

  function mountScope(config, target) {
    return Promise.all([
      fetch(config.vendor_manifest).then(function (response) {
        if (!response.ok) throw new Error("vendor manifest HTTP " + response.status);
        return response.json();
      }),
      fetch(config.inventory).then(function (response) {
        if (!response.ok) throw new Error("inventory HTTP " + response.status);
        return response.text();
      })
    ]).then(function (sources) {
      var rows = materialScopeRows(sources[1], config).concat(legalSoftwareRows(sources[0], sources[1], config));
      var category = target.querySelector("[data-scope-category]");
      var relationship = target.querySelector("[data-scope-relationship]");
      var terms = target.querySelector("[data-scope-terms]");
      var search = target.querySelector("[data-scope-search]");
      var body = target.querySelector("tbody");
      var count = target.querySelector("[data-scope-count]");

      function options(select, values, label) {
        select.replaceChildren();
        var any = document.createElement("option"); any.value = ""; text(any, label); select.appendChild(any);
        Array.from(new Set(values)).sort().forEach(function (value) {
          var option = document.createElement("option"); option.value = value; text(option, value); select.appendChild(option);
        });
      }
      function visibleRows() {
        var query = search.value.trim().toLowerCase();
        return rows.filter(function (row) {
          return (category.value === "all" || row.category === category.value) &&
            (!relationship.value || row.relationship === relationship.value) &&
            (!terms.value || row.terms === terms.value) &&
            (!query || row.cells.join(" ").toLowerCase().indexOf(query) >= 0);
        });
      }
      function dependentOptions() {
        var categoryRows = rows.filter(function (row) { return category.value === "all" || row.category === category.value; });
        options(relationship, categoryRows.map(function (row) { return row.relationship; }), "All relationships");
        options(terms, categoryRows.map(function (row) { return row.terms; }), "All recorded terms");
      }
      function paint() {
        var visible = visibleRows(); body.replaceChildren();
        visible.forEach(function (row) {
          var tr = document.createElement("tr");
          row.cells.forEach(function (value, index) {
            var td = document.createElement("td");
            if ([5, 7].indexOf(index) >= 0 && /^https?:/.test(value)) {
              var anchor = document.createElement("a"); anchor.href = value; anchor.target = "_blank";
              anchor.rel = "noopener noreferrer"; text(anchor, value); td.appendChild(anchor);
            } else text(td, value);
            tr.appendChild(td);
          }); body.appendChild(tr);
        });
        text(count, visible.length + " relationship" + (visible.length === 1 ? "" : "s"));
        target.dataset.exportReady = "1";
      }
      category.addEventListener("change", function () { dependentOptions(); paint(); });
      relationship.addEventListener("change", paint); terms.addEventListener("change", paint); search.addEventListener("input", paint);
      target.querySelector("[data-scope-download]").addEventListener("click", function () {
        var blob = new Blob([plainCsv(SCOPE_HEADER, visibleRows())], {type:"text/csv;charset=utf-8"});
        var link = document.createElement("a"); link.href = URL.createObjectURL(blob);
        link.download = "nemoclaw-legal-scope-" + category.value + ".csv";
        document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(link.href);
      });
      dependentOptions(); paint(); return rows;
    }).catch(function (error) {
      target.dataset.exportError = error.message;
      text(target.querySelector("[data-scope-count]"), "Preview failed: " + error.message);
      throw error;
    });
  }

  function boot() {
    var target = document.getElementById("third-party-export-preview");
    var scopeTarget = document.getElementById("legal-scope-preview");
    var configNode = document.getElementById("third-party-export-config");
    if ((!target && !scopeTarget) || !configNode) return;
    try {
      var config = JSON.parse(configNode.textContent);
      if (target) mount(config, target);
      if (scopeTarget) mountScope(config, scopeTarget);
    } catch (error) {
      if (target) target.dataset.exportError = error.message;
      if (scopeTarget) scopeTarget.dataset.exportError = error.message;
    }
  }

  window.ThirdPartyExportUI = { mount: mount, mountScope:mountScope, csv: csv, header: HEADER.slice(), scopeHeader:SCOPE_HEADER.slice() };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
