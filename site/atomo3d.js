// ---------------------------------------------------------------------------
// O átomo da NOVA, em 3D (o definitivo, aprovado pelo Léo em 27/10/2026;
// protótipo em prototipo-atomo-3d-v2.html): núcleo grande com malha geodésica,
// três argolas de formatos diferentes girando como moeda e oito bolinhas com
// rastro. O topo do site, a rodinha, os cards e o login usam este mesmo.
//
//   const a = criarAtomo(canvas, { cor: () => [77, 163, 255] });
//   a.passo(dt)   // anda e desenha um quadro
//
// `fundo: 0x000000` é para os átomos pequenos: o canvas usa
// `mix-blend-mode: screen`, então o preto some e só a luz aparece (sem o
// quadrado em volta, em cima de qualquer fundo).
// Sem 3D no PC, `new THREE.WebGLRenderer` dá erro: quem chama trata.
// ---------------------------------------------------------------------------
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

const RN = 0.62;       // raio do núcleo (grande)
const DIAMETRO = 4;    // o átomo inteiro, com a folga do brilho

const RUIDO = `
  vec3 m289(vec3 x){return x-floor(x*(1./289.))*289.;} vec4 m289(vec4 x){return x-floor(x*(1./289.))*289.;}
  vec4 perm(vec4 x){return m289(((x*34.)+1.)*x);} vec4 tis(vec4 r){return 1.79284291400159-.85373472095314*r;}
  float snoise(vec3 v){const vec2 C=vec2(1./6.,1./3.);const vec4 D=vec4(0.,.5,1.,2.);
    vec3 i=floor(v+dot(v,C.yyy));vec3 x0=v-i+dot(i,C.xxx);vec3 g=step(x0.yzx,x0.xyz);vec3 l=1.-g;
    vec3 i1=min(g.xyz,l.zxy);vec3 i2=max(g.xyz,l.zxy);vec3 x1=x0-i1+C.xxx;vec3 x2=x0-i2+C.yyy;vec3 x3=x0-D.yyy;
    i=m289(i);vec4 p=perm(perm(perm(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
    float n_=.142857142857;vec3 ns=n_*D.wyz-D.xzx;vec4 j=p-49.*floor(p*ns.z*ns.z);vec4 x_=floor(j*ns.z);vec4 y_=floor(j-7.*x_);
    vec4 x=x_*ns.x+ns.yyyy;vec4 y=y_*ns.x+ns.yyyy;vec4 h=1.-abs(x)-abs(y);vec4 b0=vec4(x.xy,y.xy);vec4 b1=vec4(x.zw,y.zw);
    vec4 s0=floor(b0)*2.+1.;vec4 s1=floor(b1)*2.+1.;vec4 sh=-step(h,vec4(0.));vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
    vec3 p0=vec3(a0.xy,h.x);vec3 p1=vec3(a0.zw,h.y);vec3 p2=vec3(a1.xy,h.z);vec3 p3=vec3(a1.zw,h.w);
    vec4 norm=tis(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
    vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);m=m*m;
    return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));}`;

// As argolas: três a 0°, 60° e 120°, cada uma com um formato:
//   0. a externa: faixa larga, bordas acesas, marcações e 3 partes com vãos;
//   1. a interna: fio duplo fino e tracejado;
//   2. a do meio: elipse alongada, com pontos de luz ao longo dela.
// Cada uma gira em torno do próprio eixo comprido (como uma moeda girando em
// pé) e leva as suas bolinhas, espalhadas por igual, cada uma com o rastro.
const FORMATOS = [
  { raio: 1.62, largura: .12, elipse: [1, 1],      bola: .05,  bolinhas: 3, vel: .13, giro: .5 },
  { raio: 1.3,  largura: .05, elipse: [1, 1],      bola: .038, bolinhas: 2, vel: .17, giro: -.42 },
  { raio: 1.45, largura: .08, elipse: [1.16, .84], bola: .044, bolinhas: 3, vel: .15, giro: .6 },
];

const argolaMat = (tom, fase, estilo) => new THREE.ShaderMaterial({
  uniforms: { uCor: { value: tom }, uFase: { value: fase }, uEstilo: { value: estilo } },
  transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
  vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: `uniform vec3 uCor; uniform float uFase, uEstilo; varying vec2 vUv;
    float linha(float w, float onde, float larg){ return exp(-pow((w - onde) / larg, 2.)); }
    void main(){
      float w = vUv.y;   // através da faixa (0 a 1)
      float a = vUv.x;   // em volta da argola (0 a 1)
      float luz, mostra;
      if (uEstilo < .5) {
        float s = fract(a * 3. + uFase);
        mostra = smoothstep(.0, .01, s) * (1. - smoothstep(.95, .96, s));
        float risco = (1. - smoothstep(.0, .14, fract(a * 180.))) * step(.3, w) * step(w, .7);
        luz = linha(w, .06, .04) + linha(w, .94, .04) + .08 + risco * .5;
      } else if (uEstilo < 1.5) {
        mostra = step(fract(a * 48. + uFase), .62);
        luz = (linha(w, .25, .06) + linha(w, .75, .06)) * 1.1;
      } else {
        float s = fract(a * 6. + uFase);
        mostra = smoothstep(.0, .008, s) * (1. - smoothstep(.975, .983, s));
        float conta = exp(-pow((fract(a * 18. + uFase) - .5) / .018, 2.)) * linha(w, .5, .3);
        luz = linha(w, .1, .05) + linha(w, .9, .05) + .05 + conta * 1.6;
      }
      gl_FragColor = vec4(uCor * luz * mostra, 1.);
    }`,
});

// O rastro de cada bolinha: um tubo de luz que segue a argola ATRÁS dela,
// afinando e apagando até a ponta. É montado com a bolinha em u = 0 e depois
// só gira junto (girar em Z anda pela argola: u -> (R sen, -R cos, 0)).
class Rastro extends THREE.Curve {
  constructor(r, comprimento, sentido) { super(); this.r = r; this.comprimento = comprimento; this.sentido = sentido; }
  getPoint(t, alvo = new THREE.Vector3()) {
    const u = -this.sentido * this.comprimento * (1 - t) * 6.2831853;   // t = 1 é a bolinha
    return alvo.set(Math.sin(u) * this.r, -Math.cos(u) * this.r, 0);
  }
}
const rastroMat = (tom, grossura) => new THREE.ShaderMaterial({
  uniforms: { uCor: { value: tom }, uGrossura: { value: grossura } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  vertexShader: `uniform float uGrossura; varying float vU;
    void main(){ vU = uv.x;
      vec3 p = position - normal * uGrossura * (1. - mix(.12, 1., vU));   // afina até a ponta
      gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.); }`,
  fragmentShader: `uniform vec3 uCor; varying float vU;
    void main(){ float k = pow(vU, 1.8); gl_FragColor = vec4(mix(uCor, vec3(1.), k * .45) * k * 1.9, k); }`,
});

// O halo macio em volta do núcleo (um sprite com gradiente).
function textura(r0, a0) {
  const c = document.createElement("canvas"); c.width = c.height = 256;
  const g = c.getContext("2d"), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, `rgba(255,255,255,${a0})`); gr.addColorStop(r0, "rgba(255,255,255,.18)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace;  // sem isso, o fim do degradê virava um quadrado cinza
  return tx;
}

/**
 * cor:        função que devolve [r, g, b] (0 a 255) a cada quadro
 * palco:      no topo do site, o elemento onde o átomo fica centrado (o canvas
 *             é maior que ele, para o brilho se espalhar); sem palco, o átomo
 *             ocupa o canvas
 * fundo:      a cor de fundo (0x000000 nos pequenos, com `screen`)
 * poeira:     os pontinhos fracos em volta (só no grande)
 * inclinacao: função que devolve {x, y} de -0.5 a 0.5 (o mouse), ou null
 * parado:     quem pediu menos movimento no sistema
 * traco:      engrossa argolas, bolinhas e rastros (os ícones pequenos usam 3)
 * brilho:     a força do brilho em volta (nos pequenos, menos: senão vira uma bolha)
 */
export function criarAtomo(canvas, { cor, palco = null, fundo = 0x05070b, poeira = false, inclinacao = null, parado = false, traco = 1, brilho = 1 } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.NoToneMapping;  // com ACES o fundo ficava mais escuro que a página
  const rgb = cor();
  const tom = new THREE.Color().setRGB(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, THREE.SRGBColorSpace);
  const cena = new THREE.Scene();
  // O fundo pela cena (e não setClearColor): com o bloom no meio, a cor de
  // limpeza era convertida para sRGB duas vezes e o fundo saía cinza-azulado.
  cena.background = new THREE.Color(fundo);
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  const atomo = new THREE.Group();
  cena.add(atomo);

  // --- O núcleo: uma esfera de plasma (ruído animado) com a borda acesa --------
  const nucleoMat = new THREE.ShaderMaterial({
    uniforms: { uTempo: { value: 0 }, uCor: { value: tom } },
    vertexShader: `varying vec3 vN; varying vec3 vP; varying vec3 vV;
      void main(){ vN=normalize(normalMatrix*normal); vP=position; vec4 mv=modelViewMatrix*vec4(position,1.); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }`,
    fragmentShader: RUIDO + `uniform float uTempo; uniform vec3 uCor; varying vec3 vN; varying vec3 vP; varying vec3 vV;
      void main(){
        float n = snoise(vP*4.2 + vec3(0., uTempo*.35, uTempo*.2))*.5 + snoise(vP*9. - vec3(uTempo*.5))*.25;
        float frente = max(dot(vN, vV), 0.);
        float borda = pow(1. - frente, 2.2);
        vec3 base = uCor * (0.05 + 0.32*smoothstep(-.35,.7,n));
        vec3 miolo = mix(uCor, vec3(1.), .4) * pow(frente, 6.) * .22;
        gl_FragColor = vec4(base + miolo + uCor*borda*.7, 1.);
      }`,
  });
  const nucleo = new THREE.Group(); atomo.add(nucleo);
  nucleo.add(new THREE.Mesh(new THREE.SphereGeometry(RN * .97, 96, 96), nucleoMat));
  // A casca geodésica: os triângulos de um icosaedro subdividido, em linhas de
  // luz, com um ponto aceso em cada vértice e alguns painéis que acendem devagar.
  const geo = new THREE.IcosahedronGeometry(RN, 2);
  const linhasMat = new THREE.LineBasicMaterial({ color: tom, transparent: true, opacity: .55, blending: THREE.AdditiveBlending, depthWrite: false });
  nucleo.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 1), linhasMat));
  const nosMat = new THREE.PointsMaterial({ color: tom, size: .022, transparent: true, opacity: .9, blending: THREE.AdditiveBlending, depthWrite: false });
  nucleo.add(new THREE.Points(geo, nosMat));
  const paineis = geo.clone();  // não indexada: cada triângulo tem os seus 3 vértices
  const nFaces = paineis.attributes.position.count / 3, sorteio = new Float32Array(nFaces * 3);
  for (let f = 0; f < nFaces; f++) { const s = Math.random(); sorteio.set([s, s, s], f * 3); }
  paineis.setAttribute("sorteio", new THREE.BufferAttribute(sorteio, 1));
  const paineisMat = new THREE.ShaderMaterial({
    uniforms: { uTempo: { value: 0 }, uCor: { value: tom } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `attribute float sorteio; varying float vS; void main(){ vS=sorteio; gl_Position=projectionMatrix*modelViewMatrix*vec4(position*1.002,1.); }`,
    fragmentShader: `uniform float uTempo; uniform vec3 uCor; varying float vS;
      void main(){ float on = smoothstep(.82, 1., sin(uTempo*.6 + vS*40.)*.5+.5); gl_FragColor = vec4(uCor*(.03 + on*.35), 1.); }`,
  });
  nucleo.add(new THREE.Mesh(paineis, paineisMat));
  const haloMat = new THREE.SpriteMaterial({ map: textura(.22, .5), color: tom, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: .32 * brilho });
  const halo = new THREE.Sprite(haloMat); halo.scale.set(3.4, 3.4, 1); atomo.add(halo);

  // --- As argolas e as bolinhas -------------------------------------------------
  const argolas = FORMATOS.map((F, i) => {
    const fora = new THREE.Group(); fora.rotation.z = i * Math.PI / 3; atomo.add(fora);
    const plano = new THREE.Group(); plano.rotation.x = 1.2; fora.add(plano);
    const forma = new THREE.Group(); forma.scale.set(F.elipse[0], F.elipse[1], 1); plano.add(forma);
    const sentido = i === 1 ? -1 : 1;
    // A faixa "em pé" (um aro, como um cilindro curtinho): vista de lado ela
    // continua larga, em vez de sumir numa linha.
    const aro = new THREE.CylinderGeometry(F.raio, F.raio, F.largura * traco, 512, 1, true); aro.rotateX(Math.PI / 2);
    forma.add(new THREE.Mesh(aro, argolaMat(tom, i * .37, i)));
    const eletronMat = new THREE.MeshBasicMaterial({ color: tom.clone().lerp(new THREE.Color(1, 1, 1), .5) });
    const bola = F.bola * Math.sqrt(traco), bolaGeo = new THREE.SphereGeometry(bola, 24, 24);
    const rastroGeo = new THREE.TubeGeometry(new Rastro(F.raio, .55 / F.bolinhas, sentido), 160, bola * .45, 8, false);
    const rMat = rastroMat(tom, bola * .45);
    const bolinhas = [];
    for (let j = 0; j < F.bolinhas; j++) {
      const eletron = new THREE.Mesh(bolaGeo, eletronMat);
      eletron.scale.set(1 / F.elipse[0], 1 / F.elipse[1], 1);   // a bolinha continua redonda na elipse
      const rastro = new THREE.Mesh(rastroGeo, rMat);
      forma.add(rastro, eletron);
      bolinhas.push({ eletron, rastro, desloc: j / F.bolinhas });
    }
    return { plano, bolinhas, eletronMat, sentido, raio: F.raio, vel: F.vel, fase: i * .3, giro: F.giro, giroFase: 1.2 + i * .7 };
  });

  // --- Poeira: poucos pontinhos bem fracos em volta, para dar profundidade -------
  let poeiraMat = null, nuvem = null;
  if (poeira) {
    const poeiraGeo = new THREE.BufferGeometry(), N = 260, pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const u = Math.random() * 2 - 1, a = Math.random() * 6.283, r = 1.7 + Math.pow(Math.random(), 1.6) * 1.9, q = Math.sqrt(1 - u * u);
      pos.set([Math.cos(a) * q * r, u * r * .7, Math.sin(a) * q * r], i * 3);
    }
    poeiraGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    poeiraMat = new THREE.PointsMaterial({ color: tom, size: .016, transparent: true, opacity: .35, blending: THREE.AdditiveBlending, depthWrite: false });
    nuvem = new THREE.Points(poeiraGeo, poeiraMat); cena.add(nuvem);
  }

  // --- Brilho (bloom) ---------------------------------------------------------
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(cena, camera));
  // Raio curto demais deixa o brilho quadrado (o desfoque corta nas camadas pequenas).
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), .85 * brilho, .5, .3));
  composer.addPass(new OutputPass());

  // --- Tamanho: centrado no palco (ou no canvas), ocupando quase tudo dele -------
  function medir() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false); composer.setSize(w, h);
    camera.aspect = w / h;
    const c = canvas.getBoundingClientRect(), p = palco ? palco.getBoundingClientRect() : c;
    const tamanho = palco ? Math.max(160, Math.min(p.height * .96, w * .9)) : Math.min(w, h);
    const altura = DIAMETRO * h / tamanho;   // a altura visível no plano do átomo
    camera.position.z = altura / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    camera.updateProjectionMatrix();
    atomo.position.y = (.5 - (p.top - c.top + p.height / 2) / h) * altura;
    if (nuvem) nuvem.position.y = atomo.position.y;
  }
  const observa = new ResizeObserver(medir);
  observa.observe(canvas); if (palco) observa.observe(palco);
  medir();

  const BRANCO = new THREE.Color(1, 1, 1), inclina = { x: 0, y: 0 };
  let t = 3;
  function passo(dt) {
    if (!parado) t += dt;
    const c = cor();
    tom.setRGB(c[0] / 255, c[1] / 255, c[2] / 255, THREE.SRGBColorSpace);
    haloMat.color.copy(tom); linhasMat.color.copy(tom); nosMat.color.copy(tom);
    if (poeiraMat) poeiraMat.color.copy(tom);
    nucleoMat.uniforms.uTempo.value = t; paineisMat.uniforms.uTempo.value = t;
    nucleo.rotation.y = t * .12; nucleo.rotation.x = t * .05;
    for (const g of argolas) {
      for (const b of g.bolinhas) {
        const u = g.fase + t * g.vel * g.sentido + b.desloc;   // onde a bolinha está (voltas)
        // O mesmo ponto da faixa (o cilindro deitado): u -> (R sen, -R cos, 0).
        b.eletron.position.set(Math.sin(u * 6.2831853) * g.raio, -Math.cos(u * 6.2831853) * g.raio, 0);
        b.rastro.rotation.z = u * 6.2831853;
      }
      g.eletronMat.color.copy(tom).lerp(BRANCO, .5);
      g.plano.rotation.x = g.giroFase + t * g.giro;   // o eixo X do plano é o eixo comprido da argola
    }
    const alvo = inclinacao ? inclinacao() : { x: 0, y: 0 };
    inclina.x += (alvo.x - inclina.x) * .04; inclina.y += (alvo.y - inclina.y) * .04;
    atomo.rotation.y = Math.sin(t * .22) * .35 + inclina.x * .5;
    atomo.rotation.x = Math.sin(t * .17) * .12 + inclina.y * .35;
    if (nuvem) nuvem.rotation.y = t * .02;
    composer.render();
  }
  return { passo, medir, canvas };
}
