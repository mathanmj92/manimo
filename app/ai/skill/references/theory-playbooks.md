# Topic playbooks (physics and mathematics theory)

For each area: the central ideas to teach, the usual pictures, the key equations (check them against the user's textbook and level before use), the silly mistakes, and typical exam questions. Use together with `theory-explainer-pipeline.md`. Always state the domain of validity; always verify equations by dimensions and a limit.

## Classical mechanics
- **Ideas**: Newton's laws as a model; conservation laws and the symmetries behind them (Noether, in words); the Lagrangian and Hamiltonian views; oscillators; rotation; central forces.
- **Pictures**: free-body diagrams; energy bars (kinetic, potential, total); potential-energy curves with turning points; phase portraits (ellipses for the oscillator, a separatrix for the pendulum); torque and angular momentum vectors in 3D; orbits with equal areas swept.
- **Key equations**: L = T - V; Euler-Lagrange d/dt(dL/dq') - dL/dq = 0; H = sum p q' - L, q' = dH/dp, p' = -dH/dq; simple harmonic motion x'' = -omega^2 x, omega^2 = k/m; damped x(t) = A e^(-gamma t) cos(omega_d t + phi), omega_d = sqrt(omega_0^2 - gamma^2), gamma = b / 2m; torque = I alpha, L = I omega, parallel-axis I = I_cm + M d^2; effective potential for a central force; Kepler's laws.
- **Mistakes**: treating "centrifugal force" as a real force in an inertial frame; friction pointing along motion instead of against relative sliding; action and reaction drawn on the same body; torque taken about different points in one equation; energy "lost" to friction (it becomes thermal energy); crossing trajectories in phase space (they cannot cross); using omega in rpm.
- **Exam questions**: derive the equation of motion from L; period of a pendulum for small angles; energy of a damped oscillator; moment of inertia of a rod or disc; conditions for a circular orbit.

## Waves, optics and oscillations
- **Ideas**: the wave equation, superposition, standing waves and boundary conditions, interference, diffraction, polarisation, the Doppler effect.
- **Pictures**: travelling and standing waves with nodes and antinodes; two sources with path difference; phasor addition; slit patterns with intensity plot.
- **Key equations**: v = f lambda; y'' = v^2 y_xx; standing wave nodes spacing lambda/2; double slit: bright fringes d sin(theta) = m lambda, spacing about lambda D / d; single slit minima a sin(theta) = m lambda with m not zero; Malus' law I = I_0 cos^2(theta).
- **Mistakes**: using the single-slit minimum formula for maxima; counting nodes at the fixed ends wrongly; confusing path difference with phase difference (phase = 2 pi / lambda times path); forgetting the m = 0 central maximum.

## Electromagnetism
- **Ideas**: fields as properties of space; Gauss's law and symmetry; potential versus field; Faraday induction; Maxwell's equations; electromagnetic waves.
- **Pictures**: field lines and equipotentials (2D vector fields, `StreamLines`); flux through a Gaussian surface (3D); dipole fields; a changing flux and the induced current direction; E and B in a travelling wave (3D).
- **Key equations**: Gauss: closed-surface integral of E.dA = Q_enc / epsilon_0; closed-loop integral of E.dl = -d(flux of B)/dt; no magnetic monopoles: closed-surface integral of B.dA = 0; Ampere-Maxwell: closed-loop integral of B.dl = mu_0 (I + epsilon_0 dPhi_E/dt); c = 1 / sqrt(mu_0 epsilon_0); force F = q (E + v x B).
- **Mistakes**: field lines drawn as particle paths; sign of flux through an open surface; "E inside a conductor is zero" applied to non-static cases; the magnetic force does work; omitting displacement current; using a Gaussian surface without the symmetry.

## Thermodynamics
- **Ideas**: state functions, the laws, heat versus work versus temperature, reversible processes, entropy, engines.
- **Pictures**: P-V diagrams (area = work), cycles with arrows and signs, heat flows as labelled arrows, T-S diagrams; a gas in a piston.
- **Key equations**: PV = nRT = N k_B T; dU = delta Q - delta W (state your sign convention); adiabatic PV^gamma = constant; Carnot efficiency eta = 1 - T_c / T_h (kelvin); dS = delta Q_rev / T; isolated systems: Delta S >= 0.
- **Mistakes**: heat and temperature confused; sign of work not tied to the stated convention; adiabatic taken as isothermal; Celsius in efficiency or gas laws; saying entropy "always increases" for a non-isolated system; thinking a cycle's net internal-energy change is non-zero.

## Statistical mechanics
- **Ideas**: macrostate versus microstate; counting; the Boltzmann entropy; the canonical ensemble and the partition function; the Maxwell-Boltzmann distribution; equipartition; quantum statistics.
- **Pictures**: boxes of particles with a speed histogram that builds up (fixed seed); coins or two-state spins with a distribution of macrostates (binomial); energy levels with populations that change with a temperature slider; the Maxwell-Boltzmann curve with the three speeds marked; Fermi and Bose occupation curves.
- **Key equations**: S = k_B ln Omega; probability of a microstate p_i = e^(-E_i / k_B T) / Z with Z = sum over states of e^(-E_i / k_B T); <E> = -d ln Z / d beta with beta = 1 / k_B T; Helmholtz F = -k_B T ln Z; Maxwell-Boltzmann speed distribution f(v) = 4 pi (m / 2 pi k_B T)^(3/2) v^2 e^(-m v^2 / 2 k_B T); v_p = sqrt(2 k_B T / m), <v> = sqrt(8 k_B T / pi m), v_rms = sqrt(3 k_B T / m); equipartition: (1/2) k_B T per quadratic degree of freedom; Fermi-Dirac and Bose-Einstein occupation 1 / (e^((E - mu)/k_B T) +/- 1) (plus for fermions); two-level system <E> and magnetisation tanh.
- **Mistakes**: probability of a state versus of an energy level (forgetting degeneracy); the v^2 factor (the 4 pi v^2 "number of ways") forgotten in the speed distribution; v_p, <v> and v_rms mixed up; temperature of a single molecule; time average versus ensemble average; "entropy is just disorder"; Z treated as having units; beta and T confused; Boltzmann factor with the wrong sign.
- **Exam questions**: partition function of a two-level system or a harmonic oscillator; average energy; derive the speed distribution's most probable speed; compare classical and quantum statistics; count microstates for a small system.

## Quantum mechanics
- **Ideas**: the wavefunction and probability; quantisation as boundary conditions on waves; operators and observables; the uncertainty principle; superposition and measurement; spin; tunnelling; the hydrogen atom.
- **Pictures**: phase-coloured complex wavefunctions; |psi|^2 as shaded area; energy-level ladders with states drawn on them; wave packets moving and spreading (time sweep); a barrier with a decaying tail; the Bloch sphere (3D); orbital surfaces and probability clouds (3D); two-slit build-up of dots from a fixed seed.
- **Key equations**: i hbar d psi/dt = H psi; time-independent: H psi = E psi; normalisation: integral of |psi|^2 = 1; expectation <A> = integral of psi* A psi; [x, p] = i hbar; Delta x Delta p >= hbar / 2; infinite well E_n = n^2 pi^2 hbar^2 / (2 m L^2), psi_n = sqrt(2/L) sin(n pi x / L), n = 1, 2, 3 (see the worked example); harmonic oscillator E_n = (n + 1/2) hbar omega, n = 0, 1, 2; hydrogen E_n = -13.6 eV / n^2; angular momentum L^2 = l(l+1) hbar^2, L_z = m hbar; tunnelling through a thick barrier T roughly e^(-2 kappa a) with kappa = sqrt(2m(V_0 - E)) / hbar; time dependence of a stationary state e^(-i E t / hbar).
- **Mistakes**: psi treated as the probability (it is |psi|^2, a density); electrons "orbiting"; starting n at 0 for the box (and at 1 for the oscillator, which starts at 0); E proportional to n instead of n squared (box); zero-point energy forgotten; h and h-bar mixed; normalisation constant missing; superposition read as "we just do not know which"; uncertainty explained only as the disturbance of measurement; tunnelling as "borrowing energy"; wave function collapse tied to consciousness; degeneracy not counted (hydrogen has n^2 states per n, without spin).
- **Exam questions**: solve the box or the oscillator and normalise; expectation values and uncertainties; tunnelling probability estimate; selection rules and photon wavelengths between levels; spin-1/2 measurement probabilities.

## Special relativity
- **Ideas**: the two postulates; simultaneity; time dilation and length contraction; the invariant interval; energy and momentum.
- **Pictures**: light-clock thought experiment; spacetime diagrams with the light cone; the Lorentz boost of a grid; a train and the platform with two observers.
- **Key equations**: gamma = 1 / sqrt(1 - v^2 / c^2); delta t = gamma delta t_0 (proper time is the shortest); L = L_0 / gamma (proper length is the longest, along the motion); invariant s^2 = (c t)^2 - x^2; E^2 = (p c)^2 + (m c^2)^2; E = gamma m c^2.
- **Mistakes**: using the wrong frame for "proper"; length contraction applied across the motion; "mass increases" taken as the definition; adding velocities by simple sum; the twin paradox treated as symmetric.

## Mathematics (physics-facing)
- **Linear algebra**: matrices as transformations (`m.LinearTransformationScene`), determinant as area scaling, eigenvectors as directions that stay put, diagonalisation as a change of basis. Mistakes: matrix multiplication is not commutative; eigenvalue from det(A - lambda I) = 0; an eigenvector is a direction, not a unique length; rank versus determinant.
- **Calculus and series**: limits as approach; the derivative as a slope and the tangent; the integral as area; the fundamental theorem; Taylor series with the radius of convergence. Mistakes: chain rule forgotten; product rule as a product of derivatives; "+ C" forgotten; square root of x squared is |x|; dividing by something that can be zero.
- **Differential equations**: slope fields, phase portraits, the characteristic equation for constant-coefficient linear equations, the damped oscillator cases. Mistakes: general versus particular solution; applying initial conditions before adding the particular solution.
- **Fourier**: a sum of harmonics approaching a shape (`ValueTracker` on the number of terms), the Gibbs overshoot, a spectrum beside the signal. Mistakes: the period mixed with the angular frequency; the constant term and factor of two; real and complex forms.
- **Complex numbers and analysis**: Euler's formula as a point on the unit circle (`m.ComplexPlane`), multiplication as rotation and scaling, mapping a grid by f(z). Mistakes: the argument of a negative real; dividing by a complex number without the conjugate; branch of the root.
- **Probability and statistics**: sample spaces (`m.SampleSpace`), Bayes with a base rate (natural frequencies picture), the central limit theorem from fixed-seed samples. Mistakes: base-rate neglect; independent versus mutually exclusive; the gambler's fallacy; the standard deviation and the standard error confused.
- **Vector calculus**: gradient as the steepest direction (`m.NumberPlane` with arrows), divergence as net outflow, curl as circulation, Stokes and Gauss as accounting identities. Mistakes: the order of the dot and cross product; a sign of orientation; mixing the surface and the line integral.
- **Groups and symmetry** (advanced): the symmetries of a square or triangle, composition tables, subgroups. Mistakes: assuming commutativity; counting the identity.

## Suggested lesson series (each part 4 to 8 minutes)
- *Quantum mechanics 1*: why waves (the hook), the box, the oscillator, the hydrogen atom (3D), spin and the Bloch sphere (3D), measurement.
- *Statistical mechanics 1*: microstates and counting, entropy, the Boltzmann distribution, the partition function, the Maxwell-Boltzmann distribution, quantum statistics.
- *Classical mechanics 2*: Lagrangian, Hamiltonian, phase space, central forces.
- *Electromagnetism*: fields, Gauss, induction, Maxwell and waves (3D fields).
- Each series begins with a roadmap beat and ends with a recap beat that names the next part.
