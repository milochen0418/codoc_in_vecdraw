function getStyledSVG(svgId) {
    const svg = document.getElementById(svgId);
    if (!svg) return null;

    // Clone the SVG node to avoid modifying the DOM
    const clonedSvg = svg.cloneNode(true);

    // Get all elements from the original and cloned SVG
    // We need to traverse them in parallel to copy computed styles
    const originalElements = svg.getElementsByTagName('*');
    const clonedElements = clonedSvg.getElementsByTagName('*');

    // Styles to preserve
    const stylesToCopy = [
        "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
        "font-family", "font-size", "font-weight", "font-style", "text-anchor", "dominant-baseline",
        "opacity", "visibility"
    ];

    // Copy styles from root
    const rootStyle = window.getComputedStyle(svg);
    stylesToCopy.forEach(prop => {
        clonedSvg.style[prop] = rootStyle.getPropertyValue(prop);
    });

    // Copy styles for all descendants
    for (let i = 0; i < originalElements.length; i++) {
        const original = originalElements[i];
        const cloned = clonedElements[i];
        
        const computedStyle = window.getComputedStyle(original);
        
        stylesToCopy.forEach(prop => {
            const value = computedStyle.getPropertyValue(prop);
            // Only apply if it has a value
            if (value) {
                cloned.style[prop] = value;
            }
        });
    }

    return clonedSvg;
}

function serializeSVG(svgNode) {
    const serializer = new XMLSerializer();
    let source = serializer.serializeToString(svgNode);
    
    // Add name spaces.
    if(!source.match(/^<svg[^>]+xmlns="http\:\/\/www\.w3\.org\/2000\/svg"/)){
        source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
    }
    if(!source.match(/^<svg[^>]+xmlns:xlink="http\:\/\/www\.w3\.org\/1999\/xlink"/)){
        source = source.replace(/^<svg/, '<svg xmlns:xlink="http://www.w3.org/1999/xlink"');
    }
    
    return source;
}

window.exportSVG = function() {
    const styledSvg = getStyledSVG("main-svg");
    if (!styledSvg) {
        console.error("SVG element not found");
        return;
    }

    let source = serializeSVG(styledSvg);

    // Add xml declaration
    source = '<?xml version="1.0" standalone="no"?>\r\n' + source;

    const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(source);
    
    const downloadLink = document.createElement("a");
    downloadLink.href = url;
    downloadLink.download = "drawing.svg";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

window.exportPNG = function() {
    const styledSvg = getStyledSVG("main-svg");
    if (!styledSvg) {
        console.error("SVG element not found");
        return;
    }
    
    const source = serializeSVG(styledSvg);
    
    const img = new Image();
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(source);
    
    img.onload = function() {
        const canvas = document.createElement('canvas');
        // Use the original SVG for dimensions
        const originalSvg = document.getElementById("main-svg");
        const rect = originalSvg.getBoundingClientRect();
        
        // Handle high DPI screens
        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        
        ctx.fillStyle = "white";
        ctx.fillRect(0, 0, rect.width, rect.height);
        
        ctx.drawImage(img, 0, 0, rect.width, rect.height);
        
        const imgURL = canvas.toDataURL('image/png');
        
        const downloadLink = document.createElement("a");
        downloadLink.href = imgURL;
        downloadLink.download = "drawing.png";
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
    }
}

window.exportJSON = function(data) {
    if (!data) {
        console.error("No data to export");
        return;
    }
    
    let jsonString;
    if (typeof data === 'string') {
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
    
    const downloadLink = document.createElement("a");
    downloadLink.href = url;
    downloadLink.download = "drawing.json";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
    
    // Release the URL object
    URL.revokeObjectURL(url);
}
