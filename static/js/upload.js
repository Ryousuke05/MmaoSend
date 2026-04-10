document.getElementById("fileInput").addEventListener("change", function() {
    let t = "";
    for (let f of this.files) {
        t += f.name + "<br>";
    }
    document.getElementById("list").innerHTML = t;
});