# ASCII Diagram Examples

## Example 1 (Simple)

```text
       INICIO
         │
    [Secuencial]
   Check Versión
         │
         ▼
   Login (Token) ──┐ 1.5s de espera
         │         │
         ▼         │
    [Paralelo] ◄───┘
 ┌───────┼───────┐
Datos   Cart   Wishlist ──┐
                         │
                    [Secuencial]
                   Obtener IDs
                         │
                         ▼
                   Obtener Info
```

## Example 2 (Fancy)

```text
┌─────────────────────────────────────────────────────────────────┐
│                     DEEP LINK INGRESA A LA APP                  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
        ┌───────▼────────┐             ┌───────▼────────┐
        │  Singular SDK  │             │  Firebase/     │
        │  Deferred DL   │             │  Huawei Links  │
        └───────┬────────┘             └───────┬────────┘
                │                               │
                └───────────────┬───────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   MainActivity        │
                    │   handleDeeplink()    │
                    └───────────┬───────────┘
```
