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
    "Source Author(s)", "License or Author Evidence",
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
      var source = pkg.direct ? "This project selected it directly." : "Another browser package requires it.";
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
          "Learners receive this code as part of the browser course. " + source +
            " Relationship: " + relationship + ". Used for: " + pkg.purpose + " Browser file(s): " +
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
          "Category: " + scope + ". Course authors download this package while building the browser course. " +
            (scope === "browser-bundle-input" ? "Some of its code becomes part of a generated browser file, but learners do not receive the package as a separate dependency." : "It runs only during the build; learners do not receive it.") +
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
          "Course authors or CI use this package to prepare or check the course (" + row[0] + "). " +
            "Learners do not receive it from the static course. No proprietary-code claim.",
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
          "Category: " + row[0] + ". This is an optional local-authoring or compatibility dependency. " +
            "Learners do not receive it from the static course. " + cleanEvidence,
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

  function sourceMetadata(repositoryFile, sourceUrl, documents) {
    var paper = (documents.arxiv_papers || []).find(function (item) { return item.source_url === sourceUrl; });
    if (paper) return {
      authors:paper.authors.join(", "), evidence:paper.license_url, note:paper.reuse_summary
    };
    var nvidia = (documents.nvidia_documents || []).find(function (item) {
      return (item.repository_items || []).indexOf(repositoryFile) >= 0;
    });
    if (nvidia) return {
      authors:nvidia.authors.length ? nvidia.authors.join(", ") : "No author listed on official source page",
      evidence:nvidia.author_evidence_url, note:""
    };
    return {authors:"Not recorded for this source", evidence:sourceUrl, note:""};
  }

  function materialScopeRows(markdown, documents, config) {
    return tableRows(markdown, "Third-party course-material relationships").filter(function (row) {
      return row.length >= 5;
    }).map(function (row) {
      var relationship = row[1];
      var links = parseLinks(row[4]);
      var source = links.length ? links[0].url : row[4];
      var metadata = sourceMetadata(row[0], source, documents);
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
        row[0], category, relationship, distributed, "No", source, row[3], metadata.authors,
        metadata.evidence, repoFile(config, row[0]),
        "Source label: " + row[2] + ". " + note + (metadata.note ? " " + metadata.note : "")
      ]};
    });
  }

  function documentScopeRows(documents, config) {
    var rows = (documents.arxiv_papers || []).map(function (item) {
      var evidencePath = item.cited_from[0] || "THIRD_PARTY_LICENSES.md";
      return {category:"referenced-source", relationship:"paper citation", terms:item.license, cells:[
        "arXiv:" + item.arxiv_id, "referenced-source", "paper citation",
        "No - the paper is linked, not copied by this record", "No", item.source_url, item.license,
        item.authors.join(", "), item.license_url, repoFile(config, evidencePath),
        "Official arXiv license checked " + item.verified_on + ". " + item.reuse_summary +
          " Canonical citations: " + item.cited_from.join(", ")
      ]};
    });
    (documents.nvidia_documents || []).forEach(function (item) {
      var evidencePath = item.repository_items[0] || "THIRD_PARTY_LICENSES.md";
      rows.push({category:"referenced-source", relationship:"document source", terms:item.terms, cells:[
        item.title, "referenced-source", "document source", "See related repository-item rows", "No",
        item.source_url, item.terms,
        item.authors.length ? item.authors.join(", ") : "No author listed on official source page",
        item.author_evidence_url, repoFile(config, evidencePath),
        "Official source checked " + item.verified_on + ". Related repository items: " + item.repository_items.join(", ")
      ]});
    });
    return rows;
  }

  function legalSoftwareRows(manifest, markdown, config) {
    var rows = vendoredRows(manifest, config).map(function (row) {
      return {category:"vendored-browser-code", relationship:row.relationship, terms:row.cells[2], cells:[
        row.cells[0] + "@" + row.cells[1], "vendored-browser-code", row.relationship,
        "Yes", "Yes", row.cells[7], row.cells[2], "Not applicable to software package", row.cells[3], row.cells[8],
        "Copied into the same-origin static course; the repository license text and package source corroborate scope."
      ]};
    });
    buildRows(markdown, config).filter(function (row) {
      return row.relationship === "browser-build-only";
    }).concat(validationRows(markdown, config), localRows(markdown, config)).forEach(function (row) {
      rows.push({category:"tooling-not-distributed", relationship:row.relationship, terms:row.cells[2], cells:[
        row.cells[0] + "@" + row.cells[1], "tooling-not-distributed", row.relationship,
        "No", "No", row.cells[7], row.cells[2], "Not applicable to software package", row.cells[3] || row.cells[7],
        row.cells[8], row.cells[6]
      ]});
    });
    return rows;
  }

  function text(node, value) {
    node.textContent = String(value == null ? "" : value);
  }

  function selectedValues(container) {
    return new Set(Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(function (input) {
      return input.value;
    }));
  }

  var FILTER_LABELS = {
    softwareCategory: {
      "vendored": "Included in the course",
      "build-input": "Used only to build the course",
      "validation": "Used only to check the course",
      "local-authoring": "Optional authoring tool"
    },
    softwareRelationship: {
      "direct": "Chosen directly by this project",
      "transitive": "Required by another package",
      "browser-bundle-input": "Built into the browser course",
      "browser-build-only": "Runs only while building browser files",
      "browser binary": "Browser used for automated checks",
      "workspace-runtime": "Runs in the optional author workspace",
      "material-tooling": "Processes course materials",
      "security-tooling": "Checks dependencies and security",
      "sandbox-admin-runtime": "Runs the sandbox administration service",
      "service base image": "Starting image for a local service",
      "workspace base image": "Starting image for the author workspace",
      "workspace OS packages": "Operating-system packages in the author workspace",
      "router OS packages": "Operating-system packages in the local router",
      "OpenClaw runtime": "Runs OpenClaw in the optional local stack",
      "OpenClaw OS packages": "Operating-system packages in the OpenClaw image",
      "OpenShell build image": "Image used to build OpenShell locally",
      "OpenShell runtime image": "Image used to run OpenShell locally",
      "policy engine": "Evaluates local sandbox policy"
    },
    scopeCategory: {
      "referenced-source": "Referenced, not copied",
      "tooling-not-distributed": "Used by authors or checks, not given to learners",
      "recreated-asset": "Recreated by the course authors",
      "vendored-material": "Copied into the course",
      "vendored-browser-code": "Browser code shipped to learners"
    },
    scopeRelationship: {
      "recreation": "Recreated from a source",
      "conversion": "Copied into another format",
      "summary": "Summarized",
      "inspiration": "Used as inspiration",
      "compilation": "Collected as links or references",
      "original": "Original source",
      "original course graphic": "Original course graphic",
      "paper citation": "Research paper citation",
      "document source": "NVIDIA document record",
      "direct": "Chosen directly by this project",
      "transitive": "Required by another package",
      "browser-build-only": "Used only to build browser files",
      "validation or authoring dependency": "Used to check or author the course",
      "local-authoring declaration": "Optional local-authoring dependency"
    },
    license: {
      "NOASSERTION": "Needs source-specific review"
    }
  };

  function friendlyChoice(value, kind) {
    var labels = FILTER_LABELS[kind] || {};
    var main = labels[value];
    if (!main && kind === "softwareRelationship" && value.indexOf(",") >= 0) {
      main = value.split(",").map(function (part) {
        var clean = part.trim(); return labels[clean] || clean;
      }).join(" + ");
    }
    return { main:main || value, detail:main ? value : "" };
  }

  function preferredOrder(values, preferred) {
    var rank = new Map(preferred.map(function (value, index) { return [value, index]; }));
    return values.slice().sort(function (left, right) {
      var a = rank.has(left) ? rank.get(left) : preferred.length;
      var b = rank.has(right) ? rank.get(right) : preferred.length;
      return a - b || left.localeCompare(right);
    });
  }

  function choiceGroup(container, values, selected, onChange, kind) {
    container.replaceChildren();
    var actions = document.createElement("span"); actions.className = "filter-actions";
    var all = document.createElement("button"); all.type = "button"; text(all, "Select all");
    var none = document.createElement("button"); none.type = "button"; text(none, "Clear");
    actions.append(all, none); container.appendChild(actions);
    var chips = document.createElement("span"); chips.className = "filter-chips"; container.appendChild(chips);
    values.forEach(function (value) {
      var label = document.createElement("label"); label.className = "filter-chip";
      var input = document.createElement("input"); input.type = "checkbox"; input.value = value;
      input.checked = selected.has(value); input.addEventListener("change", onChange);
      var words = friendlyChoice(value, kind);
      var caption = document.createElement("span"); caption.className = "filter-label";
      var main = document.createElement("span"); text(main, words.main); caption.appendChild(main);
      if (words.detail) {
        var detail = document.createElement("small"); text(detail, words.detail); caption.appendChild(detail);
      }
      label.append(input, caption); chips.appendChild(label);
    });
    function updateSummary() {
      var summary = container.closest("details");
      var count = summary && summary.querySelector("[data-filter-count]");
      if (count) text(count, selectedValues(container).size + "/" + values.length);
    }
    container.querySelectorAll('input[type="checkbox"]').forEach(function (input) {
      input.addEventListener("change", updateSummary);
    });
    updateSummary();
    all.addEventListener("click", function () {
      chips.querySelectorAll('input[type="checkbox"]').forEach(function (input) { input.checked = true; });
      updateSummary(); onChange();
    });
    none.addEventListener("click", function () {
      chips.querySelectorAll('input[type="checkbox"]').forEach(function (input) { input.checked = false; });
      updateSummary(); onChange();
    });
  }

  function sortedRows(rows, state) {
    if (state.index == null) return rows.slice();
    var direction = state.direction === "desc" ? -1 : 1;
    return rows.map(function (row, index) { return {row:row, index:index}; }).sort(function (left, right) {
      var compared = String(left.row.cells[state.index] || "").localeCompare(
        String(right.row.cells[state.index] || ""), undefined, {numeric:true, sensitivity:"base"}
      );
      return compared ? compared * direction : left.index - right.index;
    }).map(function (item) { return item.row; });
  }

  function sortableHeaders(table, state, onChange, sortIndexes) {
    table.querySelectorAll("thead th").forEach(function (th, index) {
      var sortIndex = sortIndexes ? sortIndexes[index] : index;
      var label = th.textContent.trim(); th.replaceChildren(); th.setAttribute("aria-sort", "none");
      var button = document.createElement("button"); button.type = "button"; button.dataset.sortIndex = String(sortIndex);
      button.className = "sort-button"; button.setAttribute("aria-label", "Sort by " + label);
      var caption = document.createElement("span"); text(caption, label);
      var arrow = document.createElement("span"); arrow.className = "sort-arrow"; text(arrow, "↕");
      button.append(caption, arrow); th.appendChild(button);
      button.addEventListener("click", function () {
        if (state.index === sortIndex) state.direction = state.direction === "asc" ? "desc" : "asc";
        else { state.index = sortIndex; state.direction = "asc"; }
        table.querySelectorAll("thead th").forEach(function (item) { item.setAttribute("aria-sort", "none"); });
        table.querySelectorAll(".sort-arrow").forEach(function (item) { text(item, "↕"); });
        th.setAttribute("aria-sort", state.direction === "asc" ? "ascending" : "descending");
        text(arrow, state.direction === "asc" ? "↑" : "↓"); onChange();
      });
    });
  }

  function externalLink(url, label) {
    var anchor = document.createElement("a"); anchor.href = url; anchor.target = "_blank";
    anchor.rel = "noopener noreferrer"; text(anchor, label || url); return anchor;
  }

  function tableCell(label) {
    var td = document.createElement("td"); td.dataset.label = label; return td;
  }

  function stacked(primary, secondary) {
    var wrapper = document.createElement("span"); wrapper.className = "cell-stack";
    var top = document.createElement("strong"); text(top, primary); wrapper.appendChild(top);
    if (secondary) { var small = document.createElement("small"); text(small, secondary); wrapper.appendChild(small); }
    return wrapper;
  }

  function evidenceDetails(summary, lines) {
    var details = document.createElement("details"); details.className = "row-evidence";
    var heading = document.createElement("summary"); text(heading, summary); details.appendChild(heading);
    lines.forEach(function (line) {
      var paragraph = document.createElement("p");
      if (line.url) paragraph.appendChild(externalLink(line.url, line.label)); else text(paragraph, line.label);
      details.appendChild(paragraph);
    });
    return details;
  }

  function renderSoftwareRow(row) {
    var tr = document.createElement("tr"), td;
    td = tableCell("Component"); td.appendChild(stacked(row.cells[0], row.cells[1])); tr.appendChild(td);
    td = tableCell("License"); td.appendChild(externalLink(row.cells[3], row.cells[2])); tr.appendChild(td);
    td = tableCell("Learner delivery"); td.appendChild(stacked(friendlyChoice(row.category, "softwareCategory").main,
      friendlyChoice(row.relationship, "softwareRelationship").main)); tr.appendChild(td);
    td = tableCell("Purpose"); text(td, row.cells[6]); tr.appendChild(td);
    td = tableCell("Evidence"); td.appendChild(evidenceDetails("Open evidence", [
      {url:row.cells[7], label:"Upstream package"}, {url:row.cells[8], label:"Repository evidence"}
    ])); tr.appendChild(td);
    return tr;
  }

  function renderScopeRow(row) {
    var tr = document.createElement("tr"), td;
    td = tableCell("Item"); td.appendChild(stacked(row.cells[0], friendlyChoice(row.relationship, "scopeRelationship").main)); tr.appendChild(td);
    td = tableCell("Use and delivery"); td.appendChild(stacked(friendlyChoice(row.category, "scopeCategory").main,
      row.cells[3] + (row.cells[4] === "Yes" ? "; runs in learner browser" : ""))); tr.appendChild(td);
    td = tableCell("Source and terms"); td.appendChild(externalLink(row.cells[5], row.cells[6])); tr.appendChild(td);
    td = tableCell("Author(s)"); text(td, row.cells[7]); tr.appendChild(td);
    td = tableCell("Evidence and notes"); td.appendChild(evidenceDetails("Open review details", [
      {url:row.cells[8], label:"Source terms or byline"}, {url:row.cells[9], label:"Repository evidence"},
      {label:row.cells[10]}
    ])); tr.appendChild(td);
    return tr;
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
      var category = target.querySelector("[data-export-category-group]");
      var relationship = target.querySelector("[data-export-relationship-group]");
      var license = target.querySelector("[data-export-license-group]");
      var search = target.querySelector("[data-export-search]");
      var base = target.querySelector("[data-export-base]");
      var body = target.querySelector("tbody");
      var count = target.querySelector("[data-export-count]");
      var sortState = {index:null, direction:"asc"};
      var categories = preferredOrder(Array.from(new Set(rows.map(function (row) { return row.category; }))), [
        "vendored", "build-input", "validation", "local-authoring"
      ]);

      function visibleRows() {
        var query = search.value.trim().toLowerCase();
        var selectedCategories = selectedValues(category);
        var selectedRelationships = selectedValues(relationship);
        var selectedLicenses = selectedValues(license);
        return rows.filter(function (row) {
          return selectedCategories.has(row.category) && selectedRelationships.has(row.relationship) &&
            selectedLicenses.has(row.cells[2]) &&
            (!query || row.cells.join(" ").toLowerCase().indexOf(query) >= 0);
        });
      }

      function relationshipOptions() {
        var selectedCategories = selectedValues(category);
        var categoryRows = Array.from(new Set(rows.filter(function (row) {
          return selectedCategories.has(row.category);
        }).map(function (row) { return row.relationship; }))).sort();
        var licenses = Array.from(new Set(rows.filter(function (row) {
          return selectedCategories.has(row.category);
        }).map(function (row) { return row.cells[2]; }))).sort();
        choiceGroup(relationship, categoryRows, new Set(categoryRows), paint, "softwareRelationship");
        choiceGroup(license, licenses, new Set(licenses), paint, "license");
      }

      function paint() {
        var visible = sortedRows(visibleRows(), sortState);
        body.replaceChildren();
        visible.forEach(function (row) {
          body.appendChild(renderSoftwareRow(row));
        });
        text(count, visible.length + " component" + (visible.length === 1 ? "" : "s"));
        target.dataset.exportReady = "1";
      }

      search.addEventListener("input", paint);
      target.querySelector("[data-export-download]").addEventListener("click", function () {
        var blob = new Blob([csv(sortedRows(visibleRows(), sortState), base.value)], { type: "text/csv;charset=utf-8" });
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "nemoclaw-third-party-components-filtered.csv";
        document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(link.href);
      });
      choiceGroup(category, categories, new Set(["vendored"]), function () { relationshipOptions(); paint(); }, "softwareCategory");
      relationshipOptions(); sortableHeaders(target.querySelector("table"), sortState, paint, [0, 2, 4, 6, 8]); paint();
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
      }),
      fetch(config.document_sources).then(function (response) {
        if (!response.ok) throw new Error("document source inventory HTTP " + response.status);
        return response.json();
      })
    ]).then(function (sources) {
      var rows = documentScopeRows(sources[2], config)
        .concat(materialScopeRows(sources[1], sources[2], config))
        .concat(legalSoftwareRows(sources[0], sources[1], config));
      var category = target.querySelector("[data-scope-category-group]");
      var relationship = target.querySelector("[data-scope-relationship-group]");
      var terms = target.querySelector("[data-scope-terms-group]");
      var search = target.querySelector("[data-scope-search]");
      var body = target.querySelector("tbody");
      var count = target.querySelector("[data-scope-count]");
      var sortState = {index:null, direction:"asc"};
      var categories = preferredOrder(Array.from(new Set(rows.map(function (row) { return row.category; }))), [
        "vendored-browser-code", "vendored-material", "recreated-asset", "referenced-source", "tooling-not-distributed"
      ]);
      function visibleRows() {
        var query = search.value.trim().toLowerCase();
        var selectedCategories = selectedValues(category);
        var selectedRelationships = selectedValues(relationship);
        var selectedTerms = selectedValues(terms);
        return rows.filter(function (row) {
          return selectedCategories.has(row.category) && selectedRelationships.has(row.relationship) &&
            selectedTerms.has(row.terms) &&
            (!query || row.cells.join(" ").toLowerCase().indexOf(query) >= 0);
        });
      }
      function dependentOptions() {
        var selectedCategories = selectedValues(category);
        var categoryRows = rows.filter(function (row) { return selectedCategories.has(row.category); });
        var relationships = Array.from(new Set(categoryRows.map(function (row) { return row.relationship; }))).sort();
        var recordedTerms = Array.from(new Set(categoryRows.map(function (row) { return row.terms; }))).sort();
        choiceGroup(relationship, relationships, new Set(relationships), paint, "scopeRelationship");
        choiceGroup(terms, recordedTerms, new Set(recordedTerms), paint, "license");
      }
      function paint() {
        var visible = sortedRows(visibleRows(), sortState); body.replaceChildren();
        visible.forEach(function (row) {
          body.appendChild(renderScopeRow(row));
        });
        text(count, visible.length + " relationship" + (visible.length === 1 ? "" : "s"));
        target.dataset.exportReady = "1";
      }
      search.addEventListener("input", paint);
      target.querySelector("[data-scope-download]").addEventListener("click", function () {
        var blob = new Blob([plainCsv(SCOPE_HEADER, sortedRows(visibleRows(), sortState))], {type:"text/csv;charset=utf-8"});
        var link = document.createElement("a"); link.href = URL.createObjectURL(blob);
        link.download = "nemoclaw-legal-scope-filtered.csv";
        document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(link.href);
      });
      choiceGroup(category, categories, new Set(["referenced-source", "recreated-asset", "vendored-material"]), function () { dependentOptions(); paint(); }, "scopeCategory");
      dependentOptions(); sortableHeaders(target.querySelector("table"), sortState, paint, [0, 1, 6, 7, 10]); paint(); return rows;
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
