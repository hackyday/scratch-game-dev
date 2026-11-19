#!/usr/bin/env node
/**
 * package_html.js — Convert .sb3 → standalone HTML via @turbowarp/packager.
 *
 * Setup (una volta sola, nella directory di questo script):
 *   npm install --save-exact @turbowarp/packager
 *
 * Uso:
 *   node package_html.js game.sb3 game.html                 [modalità turbo]
 *   node package_html.js game.sb3 game.html --vanilla       [modalità vanilla Scratch]
 *   node package_html.js game.sb3 game.html --fps 60 --clones 300 --stage 960x720
 *
 * Doppio beneficio:
 *  - produce un HTML giocabile autonomamente (nessun editor necessario)
 *  - SE lo sb3 è malformato, loadProject() fallisce → è anche un test di validità
 *    (usa scratch-vm vero per caricare il progetto).
 */

const fs = require('fs');
const path = require('path');

function findPackager() {
    const candidates = [
        path.join(__dirname, 'node_modules', '@turbowarp', 'packager'),
        path.join(process.cwd(), 'node_modules', '@turbowarp', 'packager'),
    ];
    for (const c of candidates) {
        try {
            return require(c);
        } catch (e) { /* try next */ }
    }
    console.error(
        'Manca @turbowarp/packager. Installalo con:\n' +
        `  cd ${__dirname} && npm install --save-exact @turbowarp/packager\n` +
        'oppure cd nella tua directory di lavoro e ripeti l\'installazione lì.'
    );
    process.exit(2);
}

function parseArgs(argv) {
    const args = { positional: [], flags: {} };
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i];
        if (a === '--vanilla') args.flags.vanilla = true;
        else if (a === '--fps') args.flags.fps = Number(argv[++i]);
        else if (a === '--clones') args.flags.clones = Number(argv[++i]);
        else if (a === '--stage') {
            const [w, h] = String(argv[++i]).split('x').map(Number);
            args.flags.stage = { width: w, height: h };
        } else if (a === '--interpolation') args.flags.interpolation = true;
        else args.positional.push(a);
    }
    return args;
}

async function main() {
    const { positional, flags } = parseArgs(process.argv.slice(2));
    const [input, output] = positional;
    if (!input || !output) {
        console.error('uso: node package_html.js input.sb3 output.html [opzioni]');
        process.exit(2);
    }
    const Packager = findPackager();

    // ---- carica il progetto (validità reale via scratch-vm)
    const projectData = fs.readFileSync(input);
    let loadedProject;
    try {
        loadedProject = await Packager.loadProject(projectData);
    } catch (err) {
        console.error('ERRORE di caricamento del progetto (sb3 malformato?):');
        console.error(err && err.message ? err.message : err);
        process.exit(1);
    }

    // ---- configura il packager (MUTA i default: non sostituire l'oggetto,
    // ---- ha campi interni richiesti come cloudVariables e controls.pause)
    const packager = new Packager.Packager();
    packager.project = loadedProject;
    packager.addons = []; // nessun addon: opzionale, es. ['gamepad', 'pointerlock']
    packager.options.turbo = !flags.vanilla;
    if (flags.fps) packager.options.fps = flags.fps;
    if (flags.clones) packager.options.maxClones = flags.clones;
    if (flags.interpolation) packager.options.interpolation = true;
    if (flags.stage) packager.options.stageSize = flags.stage;

    const progressCallback = (type, value) => {
        if (type === 'progress' && process.stdout.isTTY) {
            process.stdout.write(`\rpacking ${(value * 100).toFixed(0)}%`);
        }
    };

    const result = await packager.package(progressCallback);
    fs.writeFileSync(output, result.data);
    if (process.stdout.isTTY) process.stdout.write('\n');
    console.log(`OK: ${output} (${(result.data.length / 1024).toFixed(0)} KB, ` +
        `${flags.vanilla ? 'vanilla' : 'turbo'})`);
}

main().catch((err) => {
    console.error('FATAL:', err && err.stack ? err.stack : err);
    process.exit(1);
});
