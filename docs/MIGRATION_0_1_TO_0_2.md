# Migrating from 0.1.x to 0.2.0

- Use `./fbr34ker <subcommand>` for new automation. Legacy `-b`, `-r`, `-c`, `--verify`, `--gate`, and `--package` aliases remain available.
- Check public interface compatibility with `./fbr34ker abi-check`.
- Treat FBDP v1, handoff v4, module ABI v3, module container v1, FMBC v2, and board-description v1 as frozen for the 0.2.x line.
- Replace ad hoc raw recovery payload collections with generated family directories under `build-apple/`.
- Select an Apple profile by CPID rather than product-name guessing.
- Use `boot.img` for the self-describing FBRI bundle and `boot.raw` only when an authorized adapter explicitly requires an unwrapped payload.
- Keep exploit/entry logic outside FBR34KER and pass only validated artifacts into the authorized loader boundary.
