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
