const { spawn, execFile } = require('child_process');
const fs = require('fs');

const p = 'C:\\Users\\Yonsuncrat\\Videos\\Algorithms and Data Structures\\thoth\\venv\\Scripts\\python.exe';
console.log('exists:', fs.existsSync(p), p);
console.log('ComSpec:', process.env.ComSpec);
console.log('PATH contains python dir:', process.env.PATH.includes('venv\\Scripts'));

console.log('\\n-- spawn(p, [\"-V\"]) --');
let s = spawn(p, ['-V'], { shell: false });
s.on('error', e => console.error('spawn error:', e));
s.stdout?.on('data', d => console.log('out>', d.toString()));
s.stderr?.on('data', d => console.error('err>', d.toString()));
s.on('exit', c => console.log('spawn exit', c));

setTimeout(() => {
  console.log('\\n-- execFile(p, [\"-V\"]) --');
  try {
    let e = execFile(p, ['-V'], (err, stdout, stderr) => {
      if (err) console.error('execFile callback err:', err);
      if (stdout) console.log('execFile out>', stdout.toString());
      if (stderr) console.error('execFile err>', stderr.toString());
    });
    e.on('error', e2 => console.error('execFile error event:', e2));
  } catch (ex) {
    console.error('execFile threw sync:', ex);
  }
}, 1500);