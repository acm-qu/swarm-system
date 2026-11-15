# Swarm Hub phone app

The hub's screens as a native iOS and Android app (React Native + Expo, TypeScript), built from the phone
mockups in `design/html/phone-*.html`. It talks to the same hub as the web page, so the hub must be
running (`.\swarm` or `./swarm.sh` in the repo root) and the phone must be on the same network.

## Run it on your phone

You need [Node.js](https://nodejs.org) 20 or newer on your computer and the **Expo Go** app on your phone.

```
cd mobile
npm install
npm start
```

Scan the QR code it prints (iPhone: the Camera app; Android: inside Expo Go). On the sign-in screen, type
the hub's address (the hub prints it as "Web page" when it starts, for example `192.168.1.20:8000`) and
your hub login. The address is remembered on the phone; passwords never are.

`npm run ios` / `npm run android` open it in a simulator instead, if you have Xcode or Android Studio.

## Check a change

```
npm run lint        # code style
npm run typecheck   # TypeScript
npm test            # unit tests (Jest)
```

GitHub Actions runs the same three on every pull request that touches `mobile/`.
Add packages with `npx expo install <name>`, not `npm install`, so the version matches the Expo SDK.

## Where things are

| Folder | What is in it |
|---|---|
| `src/app/` | The screens. Each file is a route (Expo Router): `sign-in`, and inside `(app)/` Fleet (`index`), `robot/[name]`, History, Health, Settings |
| `src/components/` | Parts the screens share: `ui.tsx` (buttons, pills, cards), the top bar with Stop all, the tab bar, bottom sheets |
| `src/components/robot/` | The robot page: camera, and the Drive, Arm, Sensors, Terminal and Info tabs |
| `src/lib/` | No screens, only logic, with tests in `__tests__/`: `api.ts` (talks to the hub), `hub.tsx` (signed-in user and the robot list), `robot.ts`, `drive.ts`, `sensors.ts` |
| `src/theme.ts` | The colours from the mockups, dark and light |

## Safety rules (keep these)

- **Stop** and **Stop all** never need control, and the top bar with Stop all is drawn above every sheet.
- Drive commands are sent 10 times a second only while a stick is held. Letting go sends Stop, and so does
  leaving the Drive tab. The robot also stops by itself if commands stop arriving.
- After any Stop, a thumb still resting on a stick does nothing until it is lifted and put down again.
- Leaving a robot, or sending the app to the background, lets go of the sticks and releases control.

What the mockups show that the app doesn't do yet is listed in `TBD.md` in the repo root.
