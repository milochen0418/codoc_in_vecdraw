// Export the drawing: all of it, whatever part of the canvas is in view, and only the shapes: not
// selections, pointers or anyone's names.

// `var`: the page loads this file again each time a drawing opens.
var SVG_NS = "http://www.w3.org/2000/svg";
var EXPORT_PAD = 16;

function drawingBox(layer) {
    const box = layer.getBBox();
    return {
        x: box.x - EXPORT_PAD,
        y: box.y - EXPORT_PAD,
        width: Math.max(box.width, 1) + 2 * EXPORT_PAD,
        height: Math.max(box.height, 1) + 2 * EXPORT_PAD,
    };
}

function dataURL(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

// Images go in the file itself: outside the app their addresses mean nothing, and a picture drawn
// from an SVG in memory (the PNG export) can't load anything from elsewhere.
async function embedImages(svg) {
    for (const image of svg.querySelectorAll("image")) {
        try {
            const response = await fetch(image.getAttribute("href"));
            image.setAttribute("href", await dataURL(await response.blob()));
        } catch (e) {
            console.error("Image not exported", e);
        }
    }
}

async function drawingSVG() {
    const layer = document.getElementById("shapes-layer");
    if (!layer) {
        console.error("SVG element not found");
        return null;
    }
    const box = drawingBox(layer);
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("xmlns", SVG_NS);
    svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.width} ${box.height}`);
    svg.setAttribute("width", box.width);
    svg.setAttribute("height", box.height);

    const copy = layer.cloneNode(true);
    copy.removeAttribute("id");
    copy.removeAttribute("style");
    // What only the editor needs: the wide invisible strokes that make thin shapes easy to click.
    copy.querySelectorAll("[data-hit]").forEach((el) => el.remove());
    copy.querySelectorAll("*").forEach((el) => {
        el.removeAttribute("class");
        el.removeAttribute("data-shape");
        el.removeAttribute("pointer-events");
    });
    svg.appendChild(copy);
    await embedImages(svg);
    return { svg, box };
}

function serializeSVG(svgNode) {
    return new XMLSerializer().serializeToString(svgNode);
}

function download(href, filename) {
    const downloadLink = document.createElement("a");
    downloadLink.href = href;
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

window.exportSVG = async function() {
    const drawing = await drawingSVG();
    if (!drawing) return;

    // Add xml declaration
    const source = '<?xml version="1.0" standalone="no"?>\r\n' + serializeSVG(drawing.svg);

    download("data:image/svg+xml;charset=utf-8," + encodeURIComponent(source), "drawing.svg");
};

window.exportPNG = async function() {
    const drawing = await drawingSVG();
    if (!drawing) return;
    const { svg, box } = drawing;

    const img = new Image();
    img.onload = function() {
        const canvas = document.createElement("canvas");

        // Handle high DPI screens
        const dpr = window.devicePixelRatio || 1;
        canvas.width = box.width * dpr;
        canvas.height = box.height * dpr;

        const ctx = canvas.getContext("2d");
        ctx.scale(dpr, dpr);

        ctx.fillStyle = "white";
        ctx.fillRect(0, 0, box.width, box.height);

        ctx.drawImage(img, 0, 0, box.width, box.height);

        download(canvas.toDataURL("image/png"), "drawing.png");
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(serializeSVG(svg));
};

window.exportJSON = function(data) {
    if (!data) {
        console.error("No data to export");
        return;
    }

    let jsonString;
    if (typeof data === "string") {
        // If it's already a string, try to parse it to ensure it's valid JSON, then re-stringify for pretty print
        try {
            const obj = JSON.parse(data);
            jsonString = JSON.stringify(obj, null, 2);
        } catch (e) {
            // If parse fails, just use the string as is
            jsonString = data;
        }
    } else {
        // Convert object to JSON string with pretty printing
        jsonString = JSON.stringify(data, null, 2);
    }

    // Create a Blob from the JSON string
    const blob = new Blob([jsonString], { type: "application/json" });

    // Create a URL for the Blob
    const url = URL.createObjectURL(blob);

    download(url, "drawing.json");

    // Release the URL object
    URL.revokeObjectURL(url);
};
