import { CameraView, useCameraPermissions } from "expo-camera";
import React, { useState } from "react";
import { StyleSheet, View } from "react-native";
import { Button, IconButton, Text, useTheme} from "react-native-paper";
import { spacing } from "../../theme";

export default function QRScannerScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);

  const handleBarCodeScanned = ({ type, data }) => {
    setScanned(true);
    alert(`QR Code scanned: ${data}`);
    // Handle scanned data
  };

  if (!permission) {
    return (
      <View style={styles.container}>
        <Text>Requesting camera permission...</Text>
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <Text variant="bodyLarge" style={styles.permissionText}>
          No access to camera
        </Text>
        <Button mode="contained" onPress={requestPermission}>
          Grant Permission
        </Button>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={styles.camera}
        onBarcodeScanned={scanned ? undefined : handleBarCodeScanned}
        barcodeScannerSettings={{
          barcodeTypes: ["qr"],
        }}
      >
        <View style={styles.overlay}>
          <View style={styles.scanArea}>
            <View style={[styles.corner, styles.topLeft]} />
            <View style={[styles.corner, styles.topRight]} />
            <View style={[styles.corner, styles.bottomLeft]} />
            <View style={[styles.corner, styles.bottomRight]} />
          </View>
          <Text variant="bodyLarge" style={styles.instruction}>
            Align QR code within frame
          </Text>
        </View>
      </CameraView>

      {scanned && (
        <View style={styles.footer}>
          <Button mode="contained" onPress={() => setScanned(false)}>
            Scan Again
          </Button>
        </View>
      )}

      <IconButton
        icon="close"
        iconColor="#fff"
        size={28}
        style={styles.closeButton}
        onPress={() => navigation.goBack()}
      />
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000",
    justifyContent: "center",
    alignItems: "center",
  },
  permissionText: {
    color: "#fff",
    marginBottom: spacing.lg,
  },
  camera: {
    flex: 1,
    width: "100%",
  },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
  },
  scanArea: {
    width: 250,
    height: 250,
    position: "relative",
  },
  corner: {
    position: "absolute",
    width: 40,
    height: 40,
    borderColor: "#fff",
  },
  topLeft: {
    top: 0,
    left: 0,
    borderTopWidth: 3,
    borderLeftWidth: 3,
  },
  topRight: {
    top: 0,
    right: 0,
    borderTopWidth: 3,
    borderRightWidth: 3,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 3,
    borderRightWidth: 3,
  },
  instruction: {
    color: "#fff",
    marginTop: spacing.xl,
    textAlign: "center",
  },
  footer: {
    position: "absolute",
    bottom: spacing.xl,
    left: spacing.lg,
    right: spacing.lg,
  },
  closeButton: {
    position: "absolute",
    top: spacing.xl,
    right: spacing.md,
  },
});
