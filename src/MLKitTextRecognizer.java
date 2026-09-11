package com.personal.invoiceextractor;

import android.net.Uri;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import org.kivy.android.PythonActivity;

import java.io.File;
import java.util.concurrent.TimeUnit;

/**
 * Synchronous bridge used by Python/pyjnius.
 * The source image is read only for OCR and is not copied into app storage.
 */
public final class MLKitTextRecognizer {
    private MLKitTextRecognizer() {}

    public static String recognize(String filePath) throws Exception {
        File file = new File(filePath);
        InputImage image = InputImage.fromFilePath(
                PythonActivity.mActivity,
                Uri.fromFile(file)
        );

        TextRecognizer recognizer = TextRecognition.getClient(
                TextRecognizerOptions.DEFAULT_OPTIONS
        );
        try {
            com.google.mlkit.vision.text.Text result =
                    Tasks.await(recognizer.process(image), 30, TimeUnit.SECONDS);
            return result.getText();
        } finally {
            recognizer.close();
        }
    }
}
