# Seguridad

## Alcance

Este proyecto esta disenado para uso local con Flask y LM Studio. El servidor incluido no es un servidor de produccion y no debe exponerse directamente a Internet.

La configuracion Docker limita el puerto a `127.0.0.1`, ejecuta la imagen runtime como UID no privilegiado, usa un filesystem de solo lectura y elimina las capacidades Linux del contenedor.

## Configuracion segura

- Mantén `.env`, `.env.local`, tokens y credenciales fuera del repositorio.
- Usa [.env.example](.env.example) como plantilla, no como archivo de secretos.
- Define `ASISTENTE_API_TOKEN` mediante el entorno cuando necesites un token estable.
- No cambies el binding a `0.0.0.0` salvo que hayas configurado autenticacion, HTTPS y controles de red apropiados.
- Mantén las imagenes DHI fijadas por digest y actualizalas de forma consciente.
- Revisa las alertas de Dependabot y el workflow de CI despues de cada actualizacion.

## Reportar una vulnerabilidad

No publiques credenciales, datos privados ni detalles explotables en una issue publica. Abre un aviso privado en la pestaña **Security** del repositorio de GitHub, si esta habilitada, o contacta de forma privada con el mantenedor indicado en el perfil del repositorio.

Incluye la version afectada, los pasos para reproducir el problema y una evaluacion del impacto. No se garantiza un tiempo de respuesta concreto.